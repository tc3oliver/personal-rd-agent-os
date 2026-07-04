# Personal R&D Agent OS (RDOS)

> Model-agnostic · Privacy-aware · Evaluation-driven personal R&D agent

`rdos` is a local-first research-memory & synthesis agent that turns Markdown notes into a queryable, citable, traceable knowledge base — with explicit privacy-aware model routing.

## Why this exists

Most "local RAG" demos stop at chunk-and-embed. RDOS goes further:

- **Privacy-aware routing** — `private_raw` and `company_sensitive` data never leaves the local model. `private_summary` escalates to cloud only with explicit confirmation.
- **Citation-grounded answers** — every answer is backed by retrieved chunks; citations are validated against the local store *and* the retrieved context, so hallucinated references are caught.
- **Structured output** — Pydantic-validated JSON with one retry on failure, then a structured error. The pipeline never crashes on bad model output.
- **Traceable** — every run writes a self-contained JSONL record. `rdos trace list` / `rdos trace show <run_id>` for forensics.
- **Evaluation-driven** — a release gate (RAG recall, citation accuracy, routing correctness, privacy leakage) decides whether the project ships.

## The core loop

```
Markdown notes
  → index         (Batch 3, FakeEmbeddingProvider → swap to bge-m3 later)
  → retrieve      (Batch 4, hybrid: semantic + keyword via RRF)
  → cite          (Batch 4, validator: chunk_exists ∧ hash_matches ∧ in_retrieved_context)
  → privacy route (Batch 5, effective = max across all input sources)
  → model route   (Batch 5, local_fast | cloud_reasoning | code_specialist)
  → generate      (Batch 6, local llama.cpp OpenAI-compatible adapter)
  → structure     (Batch 6, Pydantic + retry once + structured error)
  → validate cite (Batch 4)
  → trace         (Batch 8, JSONL)
  → eval          (Batch 9, release gate)
```

## Quick start

```bash
uv sync --extra dev

# Sanity
uv run rdos --help
uv run pytest
uv run ruff check .

# Index the synthetic sample notes
uv run rdos index ./sample_data/notes

# Ask a question (uses local llama.cpp if reachable, else stub LLM)
uv run rdos ask "我之前是不是看過一篇講 RAG filtering 的文章？"

# Inspect runs
uv run rdos trace list
uv run rdos trace show <run_id>

# Run the release gate
uv run rdos eval all
```

## Layout

```
configs/        YAML configs (models, privacy policy, rag, tool policy)
docs/           Architecture spec, batch plans, local model stack
src/rdos/
  cli/          Typer CLI commands (index, search, ask, trace, eval)
  schemas/      Pydantic data contracts
  rag/          Parser, chunker, indexer, retriever, citation
  llm/          Provider interface, local llama.cpp adapter, structured output
  graph/        LangGraph-style state machine (linear wiring today)
  trace/        JSONL trace store
  eval/         Eval harness + release gate
  tools/        Tool permission layer (placeholder)
eval_sets/      Eval fixtures (rag, citation, model routing, privacy)
sample_data/    Synthetic markdown notes
data/           Runtime data (lancedb, sqlite, traces, reports)
tests/          Unit tests
scripts/        check_local_llm.sh, check_langchain_llama_cpp.py
```

## Architecture documents

- [docs/architecture.md](docs/architecture.md) — full v1 architecture spec
- [docs/batches/README.md](docs/batches/README.md) — batch-by-batch implementation plan
- [docs/local_model_stack.md](docs/local_model_stack.md) — local llama.cpp + bge-m3 endpoints

## CLI demo

```
$ uv run rdos index ./sample_data/notes
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric                 ┃ Value               ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ Indexed documents      │ 5                   │
│ Generated chunks (new) │ 24                  │
│ Skipped (duplicate)    │ 0                   │
│ SQLite path            │ data/sqlite/rdos.db │
│ LanceDB path           │ data/lancedb        │
└────────────────────────┴─────────────────────┘

$ uv run rdos ask "我之前是不是看過一篇講 RAG filtering 的文章？"
╭── Answer ──╮
│ ...        │
╰────────────╯
                          Citations
┏━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ # ┃ file    ┃ heading_path ┃ chunk_id     ┃
┡━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ 1 │ rag_…   │ RAG Filteri… │ 3d73ec220aff │
└───┴─────────┴──────────────┴──────────────┘
╭─ Routing ──────────────────╮
│ Model:    local_fast       │
│ Privacy:  private_raw      │
│ Confidence: 0.70           │
│ Run id:   158698bebea7     │
╰────────────────────────────╯

$ uv run rdos eval all
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┓
┃ Metric              ┃ Value  ┃ Target   ┃ Status ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━┩
│ rag_recall_at_5     │ 0.8000 │ gte 0.75 │ PASS   │
│ citation_accuracy   │ 0.8000 │ gte 0.70 │ PASS   │
│ ...                                                          │
│ Verdict: PASS                                                │
└──────────────────────────────────────────────────────────────┘
```

## Sample reports

- `data/reports/eval_report.md` — generated by `rdos eval all`
- `data/traces/runs.jsonl` — appended by every `rdos ask` run

## Design constraints (load-bearing)

1. **ModelRouter returns data only.** Never a callable tool-bound model. Tools and confirmation flow are decided by the orchestrator, not the router.
2. **PrivacyRouter takes the strictest level across all input sources**, not just the query. A `public` query that retrieves one `company_sensitive` chunk becomes a `company_sensitive` run.
3. **Citations are validated twice** — once against the store (does the chunk_id exist with this hash?) and once against the retrieved context (was the LLM actually looking at this chunk?).
4. **Structured output never raises** — first parse, then Pydantic validate, then retry once, then return a `StructuredError`. The workflow stays up.
5. **Indexing is idempotent** — `chunk_hash` is the dedup key; running `rdos index` twice produces zero new rows.
6. **Trace records are self-contained JSONL lines** — one line per run, no joins needed to read.

## Status

All 11 batches shipped. Release gate passes on the synthetic sample set.

```
Total tests: 82 passing
Release gate: PASS
```

## License

MIT
