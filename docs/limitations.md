# Limitations

Honest scope of v0.1.0-foundation. Categorized as **implemented**, **partially implemented**, and **planned**. Companion to [quality_baseline_v0.1.0.md](./quality_baseline_v0.1.0.md).

## Implemented

These work end-to-end and are exercised on the real clawd-research corpus.

- **Local-first runtime** — uv + pyproject, no Docker, no server. SQLite + LanceDB embedded.
- **Markdown parser** — frontmatter, title (H1 → filename), date (YYMMDD prefix), tags, `privacy_level` (default `private_raw`).
- **Heading-aware chunker** — 300–600 token budget, `chunk_hash` dedup, `chunk_id` deterministic.
- **Idempotent indexer** — `content_hash` short-circuits unchanged files; missing files marked `stale=1`.
- **Corpus presets** — `rdos index-corpus clawd-research --scope rag|agent|eval|security|devtools|all`.
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

- **No-answer framework** — `no_answer_threshold` config exists, retriever sets `no_answer_triggered`, but **threshold defaults to `0.0` (disabled)** because RRF scores are ~0.01 and per-collection calibration is not done. Calibration + release gate tracked in [Batch 20](./batches/batch-20-no-answer-calibration.md).
- **Tool approval flow** — `requires_approval` tools return `approval_required` decision correctly, but there is no `rdos approval approve` flow to resume the graph. Tracked in [Batch 19](./batches/batch-19-hitl-runtime.md).
- **`private_summary` cloud escalation** — privacy router correctly identifies the level and requires confirmation, but the confirmation flow + redaction pipeline are missing. In practice every run falls back to local. Tracked in [Batch 21](./batches/batch-21-redaction-cloud.md).
- **LangGraph checkpointer** — `InMemorySaver` works for single-session, but restart loses thread state. SQLite checkpointer lands in [Batch 19](./batches/batch-19-hitl-runtime.md).
- **Trace redaction** — trace records contain raw `user_query` / `retrieved_chunks` / `final_answer`. **Audit-confirmed (P1-2):** `grep redact src/rdos/trace/` is empty; Batch 21 delivered recognizers but did NOT wire them to trace-before-write. Fix lands in Batch 18.5 (post-audit cleanup, this branch). Until then, treat `data/traces/runs.jsonl` as containing potentially sensitive content.
- **Indexing speed** — `content_hash` check still reads every unchanged file. Fine at 2k files; would be slow at 100k. mtime-based fast path is future work.
- **Embedding cache** — when a file changes, all its chunks re-embed. chunk_hash-keyed cache would cut API calls.
- **Stale marker is informational** — stale documents stay searchable; only filtered from `list_recent_notes` and timeline queries. No "purge stale" command.
- **Citation coverage matcher** — synthesis uses 4-char overlap heuristic to attach claims to citations. A semantic matcher would catch more.

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
