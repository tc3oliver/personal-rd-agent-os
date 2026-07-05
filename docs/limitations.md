# Limitations

Honest scope of v0.1.0-foundation. Categorized as **implemented**, **partially implemented**, and **planned**. Companion to [quality_baseline_v0.1.0.md](./quality_baseline_v0.1.0.md).

## Implemented

These work end-to-end and are exercised on a configured research corpus.

- **Local-first runtime** — uv + pyproject, no Docker, no server. SQLite + LanceDB embedded.
- **Markdown parser** — frontmatter, title (H1 → filename), date (YYMMDD prefix), tags, `privacy_level` (default `private_raw`).
- **Heading-aware chunker** — 300–600 token budget, `chunk_hash` dedup, `chunk_id` deterministic.
- **Idempotent indexer** — `content_hash` short-circuits unchanged files; missing files marked `stale=1`.
- **Corpus presets** — `rdos index-corpus research-notes --scope rag|agent|eval|security|devtools|all`.
- **Hybrid retriever** — semantic (LanceDB cosine) + keyword (SQLite FTS) via RRF; metadata filters (privacy / tags / folder / date).
- **Query rewriter** — ASCII technical-term preservation + CJK n-grams + alias expansion (`configs/rag.yaml`).
- **Citation three-way validation** — `chunk_exists ∧ hash_matches ∧ in_retrieved_context`.
- **Privacy router** — effective privacy = `max(query, chunks, tools, memory, trace)`. `private_raw` / `company_sensitive` hard-block external models.
- **Model router** — returns data-only `ModelRoutingDecision`; never binds tools.
- **Local llama.cpp adapter** — OpenAI-compatible chat + streaming + JSON mode + `enable_thinking`. `--llm-mode stub|local|auto`.
- **OpenAI-compatible embedding provider** — `bge-m3-q8_0` (1024-d), batch input. Provider/dim mismatch raises typed errors.
- **Structured output formatter** — Pydantic validation + retry once + `StructuredError`. Never raises.
- **LangGraph StateGraph runtime** — 10 nodes + `InMemorySaver` checkpointer + per-invoke `thread_id` + node-level trace.
- **JSONL trace store** — one self-contained line per run. `rdos trace list / show`.
- **Tool permission gate** — `PermissionGate` × `CapabilityBoundary` × blocked-secret-patterns (17 patterns: `.env`, `id_rsa`, …). Path traversal / symlink escape / oversized reads blocked.
- **Safe tools** — `search_notes`, `read_note`, `list_recent_notes`, `export_report` (returns `approval_required`).
- **Research apps** — `rdos research digest / topic / synthesize`. Synthesis tracks `citation_coverage`.
- **Foundation regression gate** — 8 metrics, deterministic PASS on synthetic corpus + fake provider.
- **Real corpus retrieval benchmark** — `rdos benchmark retrieval` (Recall@3/5, MRR, hit rates, p50/p95 latency).
- **Adversarial eval sets** — 50 privacy routing + 50 model routing + 40 citation cases (incl. prompt injection, fake admin, hallucinated chunk_id, stale hash).
- **Doctor command** — `rdos doctor models` 5/5 probes (chat health / generate / embedding health / dim / batch).
- **Demo scripts** — `demo_foundation.sh`, `demo_real_corpus.sh`, `demo_eval.sh`, `demo_trace.sh`.

## Partially implemented

Architecture exists, but operationally incomplete.

- **No-answer framework** — `no_answer_threshold` lives in `configs/rag.yaml:24` (default `0.0` = disabled, explicit since Batch 23). Framework + calibrator + `NO_ANSWER_GATE` are wired (`rdos eval no-answer`). Enabling in production requires per-collection calibration against real RRF score distribution; deferred until v0.3.
- **Tool approval flow** — `requires_approval` tools return `approval_required`; **HITL resume is implemented** via `rdos approval list/show/approve/deny` (Batch 19). `export_report` writes the file only after explicit approval; replay protection via idempotency_key.
- **`private_summary` cloud escalation** — privacy router correctly identifies the level and requires confirmation; HITL approval queue handles the confirmation. **Cloud adapter is intentionally NOT shipped** in v0.2 — local-first is the design constraint. `cloud_send()` shim (`src/rdos/llm/cloud_send.py`) + `validate_prompt()` last-line-of-defense are ready and tested; the actual cloud HTTP call lands in a future batch only if a use case requires it.
- **LangGraph checkpointer** — `InMemorySaver` is the default for `build_langgraph_runtime`; `SqliteSaver` factory exists at `src/rdos/graph/checkpointer.py` and is exercised by `export_graph` and Batch 19 tests. Multi-turn thread store uses SQLite (`data/threads.db`) so thread state survives CLI restarts even when LangGraph in-memory state is lost.
- **Trace redaction** — **implemented (Batch 18.5)**. `JsonlTraceStore(redact=True)` is the default; user_query / final_answer / citation quote are run through `configs/redaction.yaml` recognizers before disk write. Set `redact=False` for debug-only runs.
- **Indexing speed** — `content_hash` check still reads every unchanged file. Fine at 2k files; would be slow at 100k. mtime-based fast path is future work.
- **Embedding cache** — when a file changes, all its chunks re-embed. chunk_hash-keyed cache would cut API calls.
- **Stale marker is informational** — stale documents stay searchable; only filtered from `list_recent_notes` and timeline queries. No "purge stale" command.
- **Citation coverage matcher** — synthesis uses 4-char overlap heuristic to attach claims to citations. A semantic matcher would catch more.
- **Multi-turn carry-forward** — Batch 22 stores cited chunk_ids per thread; Batch 23 (P1-1) wires `context_for_new_turn` into the retrieval query so the keyword channel sees prior topic tokens. Stale citations are NOT auto-purged from the carry-forward; `CitationValidator` still gates every claim at answer time.

## Planned (v0.2 Trust Runtime)

Not implemented. Roadmap in [batches/README.md](./batches/README.md#phase-3--trust-runtime-v02-batch-1922).

- **HITL approval UI** ([Batch 19](./batches/batch-19-hitl-runtime.md)) — LangGraph `interrupt` / `resume` + SQLite approval queue + `rdos approval list/show/approve/deny` + replay protection.
- **No-answer calibration** ([Batch 20](./batches/batch-20-no-answer-calibration.md)) — 30+ sample eval set + per-collection thresholds + release gate (`No-answer Accuracy ≥ 0.90`).
- **Redaction + cloud escalation** ([Batch 21](./batches/batch-21-redaction-cloud.md)) — 8 recognizers (EMAIL, PHONE_TW, ID_TW, URL, COMPANY_HINT, IP, CREDIT_CARD, ADDRESS_TW) + prompt privacy validator + trace redaction.
- **Multi-turn research thread** ([Batch 22](./batches/batch-22-multi-turn.md)) — thread state + follow-up query rewrite + cited context carry-forward + memory compression + context budget.

## Planned (later versions)

- **LLM-as-judge for answer quality** — retrieval is graded, generation is not. v0.3+.
- **Plugin external sources** — GitHub issues, arXiv, Hacker News. v0.5+.
- **Web UI** — CLI first; web UI is a separate project. Not on the v0.x roadmap.
- **Multi-tenant** — single-user by design. Not on the roadmap.

## Out of scope forever

These are intentionally never implemented:

- **`run_shell`, `git_push`, `send_email`, `delete_file` tools** — dual-use; RDOS is a research assistant, not an automation framework.
- **Cloud as default provider** — local-first is the design. Cloud is opt-in for `public` / `private_summary` only.
- **Auto-purge of stale documents** — stale markers preserve trace/citation validity for old runs. A manual `rdos corpus purge` may land later, but never automatic.

## What "foundation release" means

v0.1.0 is a **foundation release**, not production-grade agent OS. Specifically:

- The trust mechanisms (privacy routing, citation validation, tool permission, trace, eval) are real and exercised.
- The end-to-end loop (Markdown → index → retrieve → cite → answer → trace → eval) works on real data.
- The user-facing flows that depend on approval / escalation / multi-turn are stubs.
- The release gate is a regression contract, not a production SLA.

If you're evaluating this for portfolio: focus on the trust mechanisms. If you're evaluating for production: wait for v0.2.
