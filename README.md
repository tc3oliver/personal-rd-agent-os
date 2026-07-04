# Personal R&D Agent OS (RDOS)

> v0.1.0-foundation · Local-first · Model-agnostic · Privacy-aware · Evaluation-driven

`rdos` is a **foundation release** of a personal R&D agent runtime: a local-first research-memory system that turns Markdown notes into a queryable, citable, traceable knowledge base with explicit privacy-aware model routing.

> **This is not a production-grade agent OS.** It is a foundation release — the trust mechanisms (privacy routing, citation validation, tool permission, trace, eval) are real and exercised on real data, but several pieces needed for production (HITL approval UI, cloud escalation redaction, multi-turn conversation) are not yet implemented. See [Known limitations](#known-limitations).

## Why this exists

Most "local RAG" demos stop at chunk-and-embed. RDOS goes further:

- **Privacy-aware routing** — `private_raw` and `company_sensitive` data never leaves the local model. `private_summary` is *allowed* to escalate to cloud but the approval flow is not implemented yet (see [Batch 19](docs/batches/batch-19-hitl-runtime.md)).
- **Citation-grounded answers** — every answer is backed by retrieved chunks; citations are validated three ways: `chunk_exists ∧ hash_matches ∧ in_retrieved_context`.
- **Structured output** — Pydantic-validated JSON, retry once on failure, then a structured error. The pipeline never crashes on bad model output.
- **Traceable** — every run writes a self-contained JSONL record. `rdos trace list` / `rdos trace show <run_id>` for forensics.
- **Evaluation-driven** — a release gate (RAG recall, citation accuracy, routing correctness, privacy leakage) decides whether the project ships.
- **Runtime tool permission** — `PermissionGate` × `CapabilityBoundary` enforce allow-lists, path-traversal guards, symlink-escape blocks, and secret-name patterns (`.env`, `id_rsa`, …) on every file tool call.

## What is real in v0.1.0

These are not demo stubs — they are exercised on the real clawd-research corpus (~2,088 files, 25 topics) with the real local model stack.

| Capability | Status |
| --- | --- |
| Real local embedding (`bge-m3-q8_0`, 1024-d) | ✅ exercised on 476 docs / ~7k chunks |
| Real local LLM (`qwythos-9b-q4`) | ✅ health-checked, used by `rdos ask --llm-mode local` |
| Real clawd-research ingestion | ✅ incremental + index reports |
| LangGraph `StateGraph` runtime + `InMemorySaver` checkpointer + thread_id | ✅ node-level trace in JSONL |
| Runtime tool permission gate (PermissionGate × CapabilityBoundary) | ✅ blocks `.env` / path traversal / symlink escape |
| Citation three-way validation | ✅ `chunk_exists ∧ hash_matches ∧ in_retrieved_context` |
| JSONL trace store (one self-contained line per run) | ✅ |
| `rdos research digest / topic / synthesize` apps | ✅ synthesis citation coverage measured |
| Adversarial eval sets (privacy / model / citation routing) | ✅ 140+ cases incl. prompt injection |

## Quality baseline

Two distinct gates — do not confuse them.

### Foundation regression gate

- **Data**: `sample_data/notes` (5 synthetic files) + `FakeEmbeddingProvider`
- **Tool**: `rdos eval all`
- **Purpose**: deterministic PASS on every commit. If this fails, something regressed.
- **Current status**: ✅ PASS (8/8 metrics)

| Metric | Target | Status |
| --- | --- | --- |
| RAG Recall@5 | ≥ 0.75 | PASS |
| Citation Accuracy | ≥ 0.70 | PASS |
| Valid Chunk Reference Rate | ≥ 0.95 | PASS |
| Structured Output JSON Validity | ≥ 0.95 | PASS |
| Model Routing Correct Rate | ≥ 0.85 | PASS |
| Privacy Policy Compliance | = 1.00 | PASS |
| Private Raw Leakage Rate | = 0 | PASS |
| Company-sensitive Leakage Rate | = 0 | PASS |

### Real corpus retrieval benchmark

- **Data**: `clawd-research` corpus, scopes `rag` + `agent` + `eval` (~5k chunks)
- **Provider**: `local-bge-m3` (real `bge-m3-q8_0`, 1024-d)
- **Tool**: `rdos benchmark retrieval --embedding-provider local-bge-m3`
- **Purpose**: real-world quality reference. Not a release gate.
- **Current status**: see [docs/quality_baseline_v0.1.0.md](docs/quality_baseline_v0.1.0.md)

| Metric | Value |
| --- | --- |
| Recall@5 | 0.73 |
| MRR | 0.69 |
| Retrieval latency p50 | 50 ms |
| Synthesize citation coverage (AgentTrace query) | 75% |

### Verified real-world queries

| Query | Top results |
| --- | --- |
| `GraphRAG VectorRAG 層次化摘要` | top 5 all GraphRAG / Context Engineering notes |
| `AgentTrace 多智能體因果圖追蹤` | top 3 AgentTrace notes + alias hit on "flight recorder" |
| `Argus LLM 六維度輸出評估框架` | top 2 Argus-LLM G-ARVIS notes |

## The core loop

```
Markdown notes
  → index         (Batch 3, FakeEmbeddingProvider → swap to bge-m3)
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

# Index the synthetic sample notes (offline-safe)
uv run rdos index ./sample_data/notes

# Ask a question (uses local llama.cpp if reachable, else stub LLM)
uv run rdos ask "我之前是不是看過一篇講 RAG filtering 的文章？"

# Inspect runs
uv run rdos trace list
uv run rdos trace show <run_id>

# Foundation regression gate
uv run rdos eval all

# Real corpus ingestion (requires local model stack — see docs/local_model_stack.md)
uv run rdos doctor models  # 5/5 PASS expected
uv run rdos index-corpus --scope rag --embedding-provider local-bge-m3 clawd-research
uv run rdos search --embedding-provider local-bge-m3 "GraphRAG VectorRAG 層次化摘要"
```

## Layout

```
configs/        YAML configs (models, privacy policy, rag, tool policy)
docs/           Architecture spec, batch plans, quality baseline, limitations, release notes
src/rdos/
  cli/          Typer CLI commands (index, index-corpus, search, ask, trace, eval, doctor, benchmark, tool, research)
  schemas/      Pydantic data contracts
  rag/          Parser, chunker, indexer, retriever, citation, query_rewriter, corpus_presets
  llm/          Provider interface, local llama.cpp adapter, structured output, runtime_mode
  graph/        LangGraph StateGraph runtime + linear legacy runner
  trace/        JSONL trace store
  eval/         Eval harness + release gate + retrieval benchmark
  tools/        PermissionGate + CapabilityBoundary + safe tools
  apps/         digest / topic / synthesize
  approvals/    (reserved for Batch 19)
eval_sets/      Eval fixtures (rag, citation, model routing, privacy, real_rag_qa, adversarial)
sample_data/    Synthetic markdown notes (5 files)
data/           Runtime data (lancedb, sqlite, traces, reports, generated) — gitignored contents
tests/          Unit + integration tests (148 passing)
scripts/        check_local_llm.sh, check_langchain_llama_cpp.py, demo_*.sh
```

## Known limitations

Honest scope of v0.1.0 — see [docs/limitations.md](docs/limitations.md) for the full list.

- **No HITL approval UI.** `export_report` and other `requires_approval` tools return `approval_required` but no interactive flow exists to grant it. Tracked in [Batch 19](docs/batches/batch-19-hitl-runtime.md).
- **No cloud escalation.** `private_summary` routes to cloud with confirmation, but the confirmation flow + redaction pipeline are not implemented. Every run falls back to local in practice. Tracked in [Batch 21](docs/batches/batch-21-redaction-cloud.md).
- **No multi-turn conversation.** Each `rdos ask` is independent. LangGraph checkpointer is wired but resume / interrupt UX is not. Tracked in [Batch 22](docs/batches/batch-22-multi-turn.md).
- **No-answer framework exists but is disabled by default.** `no_answer_threshold` is `0.0` in `configs/rag.yaml`. Calibration is tracked in [Batch 20](docs/batches/batch-20-no-answer-calibration.md).
- **Only `rag` + `agent` + `eval` scopes were benchmarked.** The remaining 22 of 25 clawd-research topics are indexed on demand but not benchmarked.
- **InMemorySaver only.** LangGraph checkpointer is in-memory; restart loses thread state.
- **v0.1.0 is a foundation release, not production-grade agent OS.**

## Architecture documents

- [docs/architecture.md](docs/architecture.md) — full v1 architecture spec
- [docs/architecture_overview.md](docs/architecture_overview.md) — high-level component map
- [docs/quality_baseline_v0.1.0.md](docs/quality_baseline_v0.1.0.md) — what was tested, what passed, what didn't
- [docs/limitations.md](docs/limitations.md) — implemented / partially implemented / planned
- [docs/release_notes/v0.1.0-foundation.md](docs/release_notes/v0.1.0-foundation.md) — release notes
- [docs/batches/README.md](docs/batches/README.md) — batch-by-batch plan (Phase 1 + Phase 2 + Phase 3 v0.2)
- [docs/local_model_stack.md](docs/local_model_stack.md) — local llama.cpp + bge-m3 endpoints
- [docs/case_studies/](docs/case_studies/) — model routing / privacy / citation / resume positioning

## Design constraints (load-bearing)

1. **ModelRouter returns data only.** Never a callable tool-bound model. Tools and confirmation flow are decided by the orchestrator, not the router.
2. **PrivacyRouter takes the strictest level across all input sources**, not just the query. A `public` query that retrieves one `company_sensitive` chunk becomes a `company_sensitive` run.
3. **Citations are validated three ways** — `chunk_exists ∧ hash_matches ∧ in_retrieved_context`.
4. **Structured output never raises** — first parse, then Pydantic validate, then retry once, then return a `StructuredError`. The workflow stays up.
5. **Indexing is idempotent** — `chunk_hash` is the dedup key; running `rdos index` twice produces zero new rows.
6. **Trace records are self-contained JSONL lines** — one line per run, no joins needed to read.
7. **Provider/dim mismatch must raise**, never silently degrade. `EmbeddingProviderMismatchError` / `EmbeddingDimensionMismatchError`.
8. **Tool permission is enforced at the boundary, not in tool bodies.** Path traversal, symlink escape, secret-name patterns blocked before the tool runs.

## Status

| Phase | Range | Status |
| --- | --- | --- |
| Phase 1 — Foundation | Batch 0–10 | ✅ shipped |
| Phase 2 — Production Realism | Batch 11–17 | ✅ shipped, tag `v0.1.0-foundation` |
| Phase 2 — Quality Baseline Docs | Batch 18 | ✅ this release |
| Phase 3 — Trust Runtime v0.2 | Batch 19–22 | planned |

```
Total tests: 148 passing
Foundation regression gate: PASS
Real corpus benchmark: recall@5 = 0.73 (3 of 25 scopes)
```

## License

MIT
