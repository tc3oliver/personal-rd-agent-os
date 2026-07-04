# Limitations

What RDOS does **not** do in v0.1.0-foundation. Read this before promising anything.

## Runtime

- **No HITL UI**. `export_report` and other tools that `requires_approval` return `approval_required` but there's no interactive flow to grant it. The decision is logged; a human must edit policy or pre-approve.
- **No multi-turn conversation**. Each `rdos ask` is independent. LangGraph checkpointer is wired but resume / interrupt UX is not.
- **No cloud escalation**. `private_summary` correctly routes to cloud **with confirmation required**, but the confirmation flow itself is unimplemented. In practice every run falls back to local.
- **InMemorySaver only**. The LangGraph checkpointer is in-memory; restart loses thread state. A SQLite checkpointer is the obvious next step.

## Retrieval

- **Fake embedding is the CI default**. Real recall numbers require `--embedding-provider local-bge-m3`.
- **Query rewriter is heuristic**. ASCII tokens + CJK n-grams + alias table. Not a learned model. Useful for known technical terms (GraphRAG, AgentTrace) but won't generalize to unseen vocabulary.
- **No learned reranker**. RRF + weights is rank-based; a cross-encoder reranker would lift recall further.
- **No answer generation eval**. `rag_recall@5` measures retrieval; LLM answer quality is not yet graded by an LLM-as-judge.

## Privacy

- **Private data is local-only by construction**, but **the runtime confirmation flow is not**. There's no UX to say "yes, escalate this private_summary run to cloud."
- **No redaction pipeline**. If a future batch adds cloud escalation, a redaction step (masking PII, scrubbing company names) must land first.
- **Tool permission gate is conservative**. `read_note` allows all four privacy levels today; in production you may want to block `read_note` on `company_sensitive` outside a specific allowed_roots set.

## Corpus ingestion

- **Incremental index uses content_hash only**. No mtime-based fast path; each unchanged file is still read for hashing. Fine at 2k files; would be slow at 100k.
- **No incremental embedding cache**. When a file changes, all its chunks get re-embedded. A chunk_hash-keyed embedding cache would cut API calls.
- **Stale marker is informational**. Stale documents stay in the SQLite/LanceDB stores; they're filtered from `list_recent_notes` and timeline queries but still searchable. A "purge stale" command would be useful.

## Eval

- **Real benchmark needs full corpus**. The 0.73 recall@5 number is computed on 3 scopes (~5k chunks). Indexing all 25 scopes would change the number.
- **No adversarial LLM judge**. Prompt-injection cases are encoded as policy-routing tests, not as live attack attempts against the LLM.
- **Citation coverage on synthesis is heuristic**. The `_attach_citations` matcher uses 4-char overlap; a real semantic match would catch more.

## Operability

- **No metrics dashboard**. `data/reports/` accumulates markdown; there's no time-series view.
- **No structured log aggregator**. Errors land in `trace.metrics.extra` and `state["errors"]`; grep is the current SRE tool.
- **No backup story for SQLite/LanceDB**. Copy the files; that's the guidance.

## What's intentionally out of scope forever

- `run_shell`, `git_push`, `send_email`, `delete_file` tools — these are dual-use and the design constraint is that RDOS is a research assistant, not an automation framework.
- Web UI — CLI first; web UI is a separate project.
- Multi-tenant — single-user, single-tenant by design.
