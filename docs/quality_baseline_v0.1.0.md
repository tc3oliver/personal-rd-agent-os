# Quality Baseline — v0.1.0-foundation

Honest snapshot of what was tested, what passed, what didn't, and what's next. Companion to [release_notes/v0.1.0-foundation.md](./release_notes/v0.1.0-foundation.md) and [limitations.md](./limitations.md).

## 1. Release identity

| Field | Value |
| --- | --- |
| Tag | `v0.1.0-foundation` |
| Release commit | `4a41a13 chore(batch-17): harden eval benchmark and portfolio release` |
| Date | 2026-07-05 |
| Total commits (Phase 1 + Phase 2) | 18 |
| Positioning | Foundation release — not production-grade |

## 2. What was tested

Two distinct test scopes — **do not conflate them**.

| Scope | Data | Provider | Purpose |
| --- | --- | --- | --- |
| Foundation regression | `sample_data/notes` (5 synthetic files) | `FakeEmbeddingProvider` (deterministic hash) | Deterministic PASS on every commit |
| Real corpus benchmark | `clawd-research` rag + agent + eval scopes (~5k chunks of 2,088 files) | `OpenAICompatibleEmbeddingProvider` (`bge-m3-q8_0`, 1024-d) | Real-world quality reference |

Unit + integration tests: **148 passing** in 1.7s. No tests depend on external services.

## 3. Foundation regression gate results

Tool: `uv run rdos eval all` against `sample_data/notes` + `fake` provider.

| Metric | Target | Value | Status |
| --- | --- | --- | --- |
| `rag_recall_at_5` | ≥ 0.75 | 1.0000 | PASS |
| `citation_accuracy` | ≥ 0.70 | 0.8000 | PASS |
| `valid_chunk_reference_rate` | ≥ 0.95 | 1.0000 | PASS |
| `structured_output_json_validity` | ≥ 0.95 | 1.0000 | PASS |
| `model_routing_correct_rate` | ≥ 0.85 | 1.0000 | PASS |
| `privacy_policy_compliance` | = 1.00 | 1.0000 | PASS |
| `private_raw_leakage_rate` | = 0 | 0.0000 | PASS |
| `company_sensitive_leakage_rate` | = 0 | 0.0000 | PASS |

**Verdict: PASS (8/8).** This is the contract for tagging `v0.1.0-foundation`.

## 4. Real corpus benchmark results

Tool: `uv run rdos benchmark retrieval --embedding-provider local-bge-m3` against `clawd-research` corpus (3 of 25 scopes indexed).

| Metric | Value | Notes |
| --- | --- | --- |
| Samples | 63 | 60 synthesis + 3 no-answer |
| Recall@3 | 0.7000 | |
| Recall@5 | 0.7333 | |
| MRR | 0.6889 | |
| Hybrid hit rate | 0.7333 | |
| No-answer accuracy | 0.0000 | no-answer threshold disabled by default — see [limitations](./limitations.md#partially-implemented) |
| Latency p50 | 50 ms | per `ask` end-to-end |
| Latency p95 | 64 ms | |

**Not a release gate.** Real-corpus numbers will shift as more scopes are indexed and the query rewriter / reranker mature.

## 5. Retrieval observations

Verified targeted queries on the real corpus (3 scopes indexed, ~5k chunks):

| Query | Result |
| --- | --- |
| `GraphRAG VectorRAG 層次化摘要` | top 5 all GraphRAG / Context Engineering notes |
| `AgentTrace 多智能體因果圖追蹤` | top 3 AgentTrace notes; rank 4 is `Litmus: AI Agent Flight Recorder` (alias hit) |
| `Argus LLM 六維度輸出評估框架` | top 2 Argus-LLM G-ARVIS notes |

Strengths:

- English technical proper-noun preservation in `query_rewriter.py` works (GraphRAG, AgentTrace, Argus, Litmus).
- CJK n-gram tokenization keeps Traditional Chinese queries searchable.

Weaknesses:

- No learned reranker. RRF + weights is rank-based.
- Keyword channel hits only when the heading text is in chunk_text (Batch 9 fix). Anything missing from chunk_text is invisible to keyword search.
- Query rewriter is heuristic; aliases must be hand-curated in `configs/rag.yaml`.

## 6. Citation validation status

`CitationValidator` enforces three-way check on every citation:

```
is_valid = chunk_exists ∧ hash_matches ∧ in_retrieved_context
```

| Check | What it catches |
| --- | --- |
| `chunk_exists` | hallucinated `chunk_id` |
| `hash_matches` | stale reference after re-index |
| `in_retrieved_context` | LLM citing chunks it wasn't shown |

Real-corpus `synthesize` run on AgentTrace query:

- 4 claims, 7 citations
- `citation_coverage` = 75% (3 of 4 claims backed by ≥1 citation)
- All citations passed three-way validation

Release gate `valid_chunk_reference_rate = 1.0000` confirms the validator itself works on the synthetic corpus.

## 7. Tool permission status

`ToolRegistry × PermissionGate × CapabilityBoundary` enforce at runtime.

| Guard | Status |
| --- | --- |
| Path traversal (`..` in path) | ✅ blocked |
| Symlink escaping `allowed_roots` | ✅ blocked |
| Secret-name pattern (`.env`, `id_rsa`, `credentials.json`, …) | ✅ blocked (17 patterns) |
| `max_bytes` overrun | ✅ blocked |
| Path outside `allowed_roots` | ✅ blocked |
| Privacy-aware allow/deny/confirm matrix | ✅ from `configs/tool_policy.yaml` |
| `export_report` approval flow | ⚠️ returns `approval_required` but no resume — see [Batch 19](./batches/batch-19-hitl-runtime.md) |

Verified on real CLI:

```
$ rdos tool read-note .env
boundary denied: path is outside all allowed_roots

$ rdos tool read-note sample_data/notes/rag_filtering.md
read 1234 bytes from /path/to/rag_filtering.md

$ rdos tool policy-check export_report --privacy private_raw
requires_approval = True
```

Dangerous tools (`run_shell`, `git_push`, `send_email`, `delete_file`) are intentionally **not implemented**.

## 8. Known limitations

Categorized in [limitations.md](./limitations.md). Highlights:

- **HITL approval UI** — not implemented. `requires_approval` tools cannot complete.
- **Cloud escalation + redaction** — not implemented. `private_summary` cannot safely escalate.
- **Multi-turn conversation** — not implemented. Each `ask` is independent.
- **No-answer framework** — exists but disabled by default (`no_answer_threshold = 0.0`).
- **InMemorySaver only** — restart loses LangGraph thread state.
- **Corpus coverage** — only 3 of 25 clawd-research scopes are benchmarked.
- **No LLM-as-judge for answer quality** — retrieval is graded, generation is not.

## 9. Recommended next work

Phase 3 — Trust Runtime v0.2 (see [batches/README.md](./batches/README.md)):

1. **[Batch 19](./batches/batch-19-hitl-runtime.md)** — HITL Approval Runtime. LangGraph `interrupt` / `resume` + SQLite checkpointer + approval queue + `rdos approval list/show/approve/deny`. Closes the `requires_approval` loop.
2. **[Batch 20](./batches/batch-20-no-answer-calibration.md)** — No-answer Calibration. Real no-answer eval set + per-collection thresholds + release gate (`No-answer Accuracy ≥ 0.90`, `False No-answer Rate ≤ 0.05`).
3. **[Batch 21](./batches/batch-21-redaction-cloud.md)** — Redaction + Cloud Escalation. 8 recognizers + `private_summary` cloud path + trace redaction.
4. **[Batch 22](./batches/batch-22-multi-turn.md)** — Multi-turn Research Thread. Thread state + follow-up rewrite + cited context carry-forward + memory compression.

After Batch 22 ships: tag `v0.2.0-trust-runtime`.
