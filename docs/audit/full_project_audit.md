# RDOS Full Project Audit Report

> Audit date: 2026-07-05
> Method: 3 parallel read-only agents (Agent 1: Batches 1–8, Agent 2: Batches 9–17 + arch, Agent 3: Batches 18–22 + security + scoring)
> Head: `86a617a feat(batch-18.5): close audit P1-1 through P1-4`
> Branch: `feat/v0.2-trust-runtime`

---

## 0. Executive Verdict

| Question | Answer |
| --- | --- |
| **Overall Status** | **Strong foundation, v0.2 has 2 P0 gaps** |
| **Release Readiness** | v0.1.0-foundation: solid. v0.2.0-trust-runtime: needs Batch 23 hardening before re-tag |
| **Recommended Next Action** | Run Batch 23 release freeze: register `rdos thread` CLI + untrack 3 runtime files + refresh stale docs. Then tag `v0.2.1-trust-runtime-hardened`. |
| **Can we stop after Batch 22?** | **No.** Two P0 issues block honest v0.2 release. |

**Headline**:
- Batches 1–17 (Phase 1+2): fully shipped, solid foundation, all PASS.
- Batches 18–22 (Trust Runtime): real implementation but Batch 22 left `rdos thread` CLI unregistered, and 3 runtime files slipped into git history despite .gitignore.
- Adversarial eval sets ARE actually executed (Batch 18.5 fix worked).
- Citation validator is real; privacy hard-block is real; tool boundary is real.
- `prompt_privacy_validator` exists but is **dead code** — cloud adapter never calls it (because there is no cloud adapter).
- `context_for_new_turn` exists but is **not wired into retrieval** — carry-forward is display-only.

---

## 1. Audit Environment

| Field | Value |
| --- | --- |
| Date | 2026-07-05 |
| Branch | `feat/v0.2-trust-runtime` |
| Head commit | `86a617a feat(batch-18.5): close audit P1-1 through P1-4` |
| Tags | `v0.1.0-foundation`, `v0.2.0-trust-runtime` |
| Python / uv | Python 3.11.8 / uv 0.9.18 |
| Local model availability | **REACHABLE** — `rdos doctor models` 5/5 PASS at `10.10.10.12:8080/8081` |
| Real corpus availability | Present at `~/Workspace/notes/AI/clawd-research`; tests use `tmp_path` (no real-corpus dependency in test suite) |

---

## 2. Command Results

| Command | Result | Notes |
| --- | --- | --- |
| `git status --short` | clean | empty |
| `git log --oneline -n 30` | all batches 0–22 + audit fixes | batch-N naming consistent |
| `git tag --list` | 2 tags | both present |
| `uv run pytest` | **215 passed, 1 warning in ~2s** | exit 0; warning is `LangChainPendingDeprecationWarning` (third-party) |
| `uv run ruff check .` | All checks passed | exit 0 |
| `uv run rdos --help` | **13 commands** | ⚠️ `thread` MISSING (Agent 3 P0-1) |
| `uv run rdos eval all` | **Verdict PASS** | 8/8 release gate; adversarial executed; opt-in gates shown |
| `uv run rdos doctor models` | **5/5 PASS** | chat_health / chat_generate / embedding_health / dim=1024 / batch=3 |
| `uv run rdos benchmark retrieval` | works (fake = 0.0 across metrics) | expected without real indexed corpus |

---

## 3. Batch Status Matrix

| Batch | Name | Status | Key Evidence | Key Risk |
| --- | --- | --- | --- | --- |
| 1 | Schema + Config | ✅ PASS | `schemas/*.py` + `config.py`; used at runtime by 4+ modules | none |
| 2 | Parser + Chunker | ✅ PASS | `markdown_parser.py:30-134`; deterministic chunk_hash; tests cover missing frontmatter | none |
| 3 | SQLite + LanceDB Index | ✅ PASS | `indexer.py:111`; typed mismatch errors; idempotent reindex verified | none |
| 4 | Hybrid Retriever + Citation | ✅ PASS | RRF + 3-way validator wired into langgraph `validate_citations` node | none |
| 5 | Privacy + Model Router | ✅ PASS | `privacy_router.py:73-77` 5-source max; router returns data only | none |
| 6 | Local LLM + Structured Output | ✅ PASS | OpenAI-compatible adapter; retry once + StructuredError; `doctor` 5/5 | none |
| 7 | Research Memory Workflow | ✅ PASS | 10 nodes + langgraph topology; linear runner kept as fallback | none |
| 8 | Trace Store | ✅ PASS | JSONL with all required fields; **redaction default ON** (Batch 18.5) | none |
| 9 | Eval + Release Gate | ✅ PASS | 8-metric gate; structured_output real; adversarial runs | adversarial visibility-only |
| 10 | Portfolio Polish | ✅ PASS | README disclaims production-grade; case studies; samples | none |
| 11 | Real Local Runtime | ✅ PASS | `OpenAICompatibleEmbeddingProvider`; provider/dim guards; `--llm-mode` works | none |
| 12 | Real Corpus Ingestion | ✅ PASS | 6 presets; incremental; index report; env override | none |
| 13 | Retrieval Hardening | ⚠️ **PARTIAL** | query_rewriter + benchmark work; **`no_answer_threshold` not in `configs/rag.yaml`** | defaults apply silently |
| 14 | LangGraph Runtime | ✅ PASS | real `StateGraph`; thread_id per invoke; node-level trace | InMemorySaver only (documented) |
| 15 | Tool Permission | ✅ PASS | PermissionGate × CapabilityBoundary; 17 secret patterns; tests cover .env / id_rsa / symlink | tools not invoked inside `rdos ask` (CLI-only) |
| 16 | Research Apps | ✅ PASS | digest / topic / synthesize; citation_coverage | privacy_level hardcoded `private_raw` |
| 17 | Hardening + Release | ✅ PASS | adversarial sets 50/55/42; demo scripts; tag | adversarial visibility-only |
| 18 | Quality Baseline Docs | ✅ PASS | quality_baseline_v0.1.0.md; honest framing | none |
| 19 | HITL Approval Runtime | ⚠️ **PARTIAL** | ApprovalQueue + interrupt/resume; replay protection | `_resume_graph` swallows exceptions silently |
| 20 | No-answer Calibration | ⚠️ **PARTIAL** | framework exists; **threshold defaults to 0** | disabled in production unless user calibrates |
| 21 | Redaction + Cloud | ⚠️ **PARTIAL** | 8 recognizers; trace redaction wired; **`validate_prompt` is dead code; no cloud adapter** | "cloud escalation" is infra-only |
| 22 | Multi-turn Thread | ❌ **FAIL — CLI unreachable** | ThreadStore + rewriter work; **`rdos thread` not registered in main app** | Batch 22 deliverable cannot be invoked |

**Summary**: 16 PASS, 4 PARTIAL, 1 FAIL.

---

## 4. Implemented Capabilities

Real, end-to-end, tested, and exercised on real data:

- ✅ Pydantic schemas + YAML config loader with env substitution
- ✅ Frontmatter parser + heading-aware chunker (deterministic chunk_hash + chunk_id)
- ✅ SQLite + LanceDB idempotent indexer (provider/dim mismatch raises typed errors)
- ✅ Hybrid retriever (semantic + keyword + RRF) with metadata filter
- ✅ Citation three-way validator (`chunk_exists ∧ hash_matches ∧ in_retrieved_context`) wired into LangGraph topology
- ✅ PrivacyRouter effective = max across 5 sources; hard-blocks `private_raw` / `company_sensitive`
- ✅ ModelRouter returns data-only decisions; never binds tools
- ✅ LocalLlamaCppAdapter OpenAI-compatible with retry-once structured output
- ✅ LangGraph StateGraph with InMemorySaver + per-invoke thread_id + node-level trace
- ✅ JSONL trace store with **redaction-before-write default ON**
- ✅ `OpenAICompatibleEmbeddingProvider` for bge-m3 (1024-d batch)
- ✅ Corpus presets (rag/agent/eval/security/devtools/all) with incremental index
- ✅ Query rewriter (ASCII preservation + CJK n-grams + alias expansion)
- ✅ Retrieval benchmark (Recall@3/5, MRR, hit rates, latency p50/p95)
- ✅ ToolRegistry × PermissionGate × CapabilityBoundary (path traversal / symlink / secrets blocked)
- ✅ Safe tools: `search_notes` / `read_note` / `list_recent_notes` / `export_report`
- ✅ Research apps: digest / topic / synthesize (with citation_coverage)
- ✅ Adversarial eval sets actually executed by `rdos eval all`
- ✅ Real corpus benchmark (recall@5=0.73, MRR=0.69, p50=50ms — 3 of 25 scopes)
- ✅ Redaction recognizers (8) with Luhn-validated credit card
- ✅ ApprovalQueue with idempotency_key + interrupt/resume + replay protection
- ✅ ThreadStore + TurnRecord + cited_chunks carry-forward

---

## 5. Partial / Missing Capabilities

### PARTIAL

- **`rdos thread` CLI** — ThreadStore + rewriter work in tests, but main `rdos` CLI does not register the typer app. `rdos thread new` returns "No such command". (Batch 22)
- **No-answer calibration** — Framework + evaluator + calibrator all exist, but `no_answer_threshold` defaults to `0.0` (disabled). Production users get hard answers regardless of retrieval score. (Batch 20)
- **Cloud escalation** — Redaction recognizers + `PromptPrivacyValidator` class exist, but: (a) no cloud adapter (no OpenAI/Anthropic sender), (b) `validate_prompt` is never called by any LLM call site — dead code. (Batch 21)
- **Multi-turn carry-forward** — `context_for_new_turn(state)` is defined but **never invoked** by `cli/thread.py` or any graph node. Cited chunks accumulate in DB but never re-enter retrieval prompt. (Batch 22)
- **Approval resume error handling** — `_resume_graph` in `cli/approval.py:154-155` uses bare `except Exception` and prints "graph resume skipped" — masks failures. (Batch 19)
- **`no_answer_threshold` not in `configs/rag.yaml`** — defaults apply silently; user-facing config surface incomplete. (Batch 13)

### NOT IMPLEMENTED (intentionally)

- ❌ Cloud adapter (OpenAI/Anthropic) — `private_summary → cloud` path is gated but no sender exists
- ❌ LLM-as-judge for answer quality (deferred to v0.3)
- ❌ Web UI (separate project)
- ❌ Plugin external sources (GitHub issues, arXiv)
- ❌ `run_shell` / `git_push` / `send_email` / `delete_file` tools (out of scope forever)
- ❌ LLM-driven memory compression (current is deterministic excerpt)
- ❌ Persistent SQLite checkpointer wired by default (factory exists, but main runtime uses InMemorySaver)

---

## 6. Architecture Consistency Findings

### Model Router — ✅ All 5 checks pass
Returns `ModelRoutingDecision` dataclass; no `bind_tools`; profile/adapter cleanly separated via `runtime_mode.resolve_llm`. Profiles `local_fast / cloud_reasoning / long_context / code_specialist` defined in `configs/models.yaml`.

### Privacy Router — ✅ 5 of 6 checks pass
- ✅ `effective = max(query + chunks + tools + memory + trace)` at `privacy_router.py:73-77`
- ✅ Retrieved private chunks escalate privacy
- ✅ `company_sensitive` and `private_raw` never external
- ✅ `private_summary` requires confirmation
- ⚠️ **Prompt privacy validator class exists but is dead code** — no LLM call site invokes `validate_prompt`

### Citation — ✅ All 5 checks pass
Three-way validator genuinely enforces `chunk_exists ∧ hash_matches ∧ in_retrieved_context`. Hash drift + hallucinated chunk_id + out-of-context all detected. Synthesis `citation_coverage` metric computed.

### Tool Safety — ✅ All 6 checks pass
17 secret patterns blocked (`.env`, `id_rsa`, `credentials`, …). Path traversal / symlink escape / `max_bytes` enforced before tool body. `export_report` returns `approval_required`. Dangerous tools not present in registry.

### Eval — ✅ All 6 checks pass
Adversarial cases **actually executed** (Batch 18.5 fix). Release gate thresholds unchanged. Real corpus benchmark cleanly separated from sample_data regression gate. Failed cases listed in `data/reports/eval_report.md`. No-answer actually evaluated (opt-in gate).

---

## 7. Security / Privacy Findings

**Public Repo Safety: PASS (with P0 hygiene fixes)**

| Check | Verdict |
| --- | --- |
| No real personal notes | ✅ `sample_data/notes/*.md` are synthetic technical notes |
| No company data | ✅ |
| No tracked secrets | ✅ only `.env.example` |
| `.env` not tracked | ✅ |
| Runtime outputs gitignored | ⚠️ `.gitignore` covers them, BUT 3 files already in history (see P0-2) |
| Trace sample redacted | ✅ `data/samples/trace_sample.jsonl` is documentation-style, no real PII |
| Sample notes synthetic | ✅ |
| Adversarial payload safe | ✅ fake papers (`XYZFakePaper2026`) + policy labels only |
| No PII logging | ✅ `grep` for `private_raw\|email\|phone\|id_tw` in `print` / `console.print` empty |
| Cloud path cannot leak `private_raw` | ✅ because **no cloud adapter exists** (no sender = no leak path) |

**Risks**:
- `data/approvals.db`, `data/samples/trace_sample.jsonl`, `data/generated/reports/synthesis_*.md` already committed before `.gitignore` rule was added — need `git rm --cached`.
- All sample files audited; no real PII found.

**Required fixes before public release**: see P0-2 below.

---

## 8. Test and Eval Findings

| Item | Result |
| --- | --- |
| Total tests | **215** passing |
| Skipped / failed | 0 / 0 |
| Slow tests | none |
| Warning | `LangChainPendingDeprecationWarning` (third-party, langgraph) |
| Adversarial eval actually runs | ✅ yes (Batch 18.5 fix confirmed) |
| Release gate silently lowered | ❌ no — thresholds match foundation spec |
| Failed cases listed in report | ✅ yes (`## Failures — <eval>` section) |

**Test-stub-only areas** (no real-model coverage):
- All Batch 19 (HITL) tests use `StubLLMAdapter`
- Batch 22 (thread) tests do not invoke real retriever — pure store/rewriter unit tests
- Redaction tests use built-in `DEFAULT_SAMPLES`, not real model output
- No test asserts `thread` is registered in main app

---

## 9. Documentation Accuracy

### Overclaimed items

1. **`docs/release_notes/v0.2.0-trust-runtime.md:7-12`** claims `rdos thread new|ask|list|show|close` shipped — but `rdos thread` is not registered. **Overclaim.**
2. **`docs/release_notes/v0.2.0-trust-runtime.md:11`** says Batch 21 ships "Cloud Escalation guardrails" — only the validator class exists; no cloud call site uses it. **Overclaim.**
3. **`docs/limitations.md:39-44`** still describes trace redaction as future ("Fix lands in Batch 18.5") — Batch 18.5 has landed; this paragraph is stale.
4. **`docs/quality_baseline_v0.1.0.md:117`** says `export_report` returns `approval_required` "but no resume — see Batch 19" — Batch 19 ships resume; caveat stale.
5. **`src/rdos/llm/redaction.py:3-4`** docstring "Used by cloud escalation (private_summary)" — there is no sender; misleading.

### Under-documented

- `rdos thread` CLI module exists in source but undocumented (because unreachable).
- `prompt_privacy_validator` exists in code but no doc says it's currently dead code.
- `no_answer_threshold` defaults to 0 — only mentioned deep in `eval/report.py:20-23`, not in `configs/rag.yaml`.

### Misleading wording

- "Trust Runtime v0.2" framing implies cloud escalation + multi-turn thread work end-to-end; in reality cloud is infra-only and thread CLI is unreachable.

---

## 10. Stop / Continue Recommendation

| Question | Answer |
| --- | --- |
| 1. Should we do Batch 18+ before v1.0? | ✅ Already done — and necessary. Quality baseline reframed release honestly. |
| 2. Are Batches 19–22 truly necessary? | Yes for "Trust Runtime" thesis. ~70% implemented. Two P0 gaps block honest release. |
| 3. After Batch 22, can we stop? | **No.** Need a small Batch 23 release freeze to fix P0s and stale docs. |
| 4. Need Batch 23 release freeze? | **Yes.** Register thread CLI, untrack runtime files, refresh limitations.md, tag `v0.2.1-trust-runtime-hardened`. |
| 5. What belongs in parking lot (do NOT do)? | LLM-as-judge (v0.3), Web UI, multi-tenant, plugin external sources, auto-purge stale docs, dangerous tools. |

---

## 11. Required Fixes Before Next Batch

### P0 — Must fix before continuing

**P0-1: Register `rdos thread` in main CLI**
- Evidence: `src/rdos/cli/__init__.py:7-18` (no `thread` import); `rdos --help` lists 13 commands, missing `thread`
- Fix: add `from rdos.cli.thread import app as thread_app` + `app.add_typer(thread_app, name="thread")`
- Files: `src/rdos/cli/__init__.py`; add test asserting `thread` is in main app commands

**P0-2: Untrack runtime files already in git history**
- Evidence: `git ls-files | grep '^data/'` returns `data/approvals.db`, `data/samples/trace_sample.jsonl`, `data/generated/reports/synthesis_20260704T175132Z.md`
- Fix: `git rm --cached` for each
- Files: repo HEAD only (no source change)

### P1 — Should fix before v1.0

**P1-1: Wire `context_for_new_turn` into retrieval (or downgrade docs)**
- Evidence: `rewriter.py:39` defined; only `rewrite_followup` used in `cli/thread.py:71`. Cited chunks accumulate in DB but never re-enter prompt.
- Fix: pass `state.cited_chunks` as a soft RetrievalFilters boost, OR prepend a "prior context" block to the prompt.

**P1-2: Make `prompt_privacy_validator.validate_prompt` live (or document it as dead code)**
- Evidence: `grep -rn 'validate_prompt' src/rdos/` returns only the definition
- Fix: Either implement a minimal cloud adapter that invokes `validate_prompt` before HTTP call, or update docs to say "redaction infra ready; cloud adapter pending"

**P1-3: Refresh stale docs**
- `docs/limitations.md:39-44` — move Batch 18.5 trace redaction from "Partially" to "Implemented"
- `docs/quality_baseline_v0.1.0.md:117` — update export_report caveat (Batch 19 shipped resume)
- `docs/release_notes/v0.2.0-trust-runtime.md` — acknowledge cloud adapter is infra-only

**P1-4: Calibrate `no_answer_threshold` or document why default is 0**
- Either run `calibrate_thresholds` on real corpus and bake into `configs/rag.yaml`, OR add one-line note that calibration is deferred to v0.3

**P1-5: Surface Batch 13 retrieval knobs in `configs/rag.yaml`**
- Currently `vector_top_k`, `keyword_top_k`, `rerank_top_k`, `no_answer_threshold`, `enable_query_rewrite`, `min_score_threshold` exist only as code defaults in `config.py:91-97`

**P1-6: Stop swallowing exceptions in `_resume_graph`**
- `src/rdos/cli/approval.py:154-155` catches bare `Exception` and prints "graph resume skipped"
- Fix: log to trace at minimum

### P2 — Parking lot (do NOT do in v0.x)

- LLM-driven memory compression (currently deterministic concat)
- Per-collection threshold auto-bake CLI
- Stale chunk_hash detection in thread carry-forward
- Cloud adapter (OpenAI / Anthropic)
- LLM-as-judge answer eval (v0.3)
- Web UI (separate project)
- Multi-tenant
- Plugin external sources

---

## 12. Scoring (0–5, strict)

| Area | Score | Reason |
| --- | --- | --- |
| Architecture alignment | **4/5** | Clean LangGraph + SQLite + LanceDB layering; Trust Runtime concept coherent |
| Real runtime readiness | **2/5** | `rdos thread` unreachable; cloud adapter absent; approval resume swallows errors |
| Retrieval quality | **4/5** | Real corpus Recall@5=0.73, MRR=0.69; no learned reranker |
| Privacy enforcement | **3/5** | Privacy router + redaction infra solid; **validator dead code**, cloud path unimplemented |
| Citation reliability | **4/5** | Three-way validator works on real corpus; coverage heuristic only |
| Tool safety | **5/5** | Permission gate, 17 secret patterns, path traversal blocked, no dangerous tools |
| Traceability | **4/5** | JSONL trace + redaction-before-write working; carry-forward not fed back |
| Eval credibility | **4/5** | Honest baseline + adversarial + opt-in gates; no LLM-as-judge |
| Documentation honesty | **3/5** | Solid foundation doc but v0.2 release notes overclaim thread + cloud; limitations.md stale |
| Portfolio readiness | **3/5** | Strong code; glaring CLI gap (thread) undermines demo |

**Total: 36/50 (72%)** — solid foundation, v0.2 release tarnished by 2 P0 gaps.

---

## 13. Suggested Next Agent Prompt — Batch 23 Release Freeze

```
You are picking up RDOS at commit 86a617a (post-Batch 22). Scope: harden and
tag v0.2.1, NOT new features. A read-only audit by principal engineer found
two P0 gaps blocking honest v0.2 release.

P0 (must):
1. Register the thread CLI. In src/rdos/cli/__init__.py add:
     from rdos.cli.thread import app as thread_app
     app.add_typer(thread_app, name="thread")
   Add tests/test_batch23_cli_wiring.py that asserts "thread" appears in
   `rdos --help` AND that `rdos thread new` creates a row in data/threads.db.

2. Untrack runtime files committed before .gitignore caught them:
     git rm --cached data/approvals.db data/samples/trace_sample.jsonl \
       data/generated/reports/synthesis_20260704T175132Z.md
   Commit with: chore(batch-23): untrack runtime artifacts

P1 (should):
3. Wire cited_chunks carry-forward into retrieval. In src/rdos/cli/thread.py
   ask_cmd, pass state.cited_chunks into the runtime as a soft preference
   (e.g., RetrievalFilters.boost_ids) OR prepend a "prior context" block to
   the prompt. Document the chosen approach in docs/batches/batch-22-multi-turn.md.

4. Replace the bare `except Exception` in src/rdos/cli/approval.py:154-155
   with structured trace logging.

5. Refresh docs/limitations.md — move trace redaction (P1-2) from "Partially
   implemented" to "Implemented". Update docs/quality_baseline_v0.1.0.md:117
   export_report caveat to point to Batch 19 (now shipped). Update
   docs/release_notes/v0.2.0-trust-runtime.md to acknowledge that cloud
   adapter is infra-only (validator + recognizers ship, sender pending).

6. Either run `rdos eval no-answer` calibration on the real corpus and bake
   the threshold into configs/rag.yaml, OR add a one-line note in
   limitations.md that calibration is deferred to v0.3.

7. Surface Batch 13 retrieval knobs in configs/rag.yaml (vector_top_k,
   keyword_top_k, rerank_top_k, no_answer_threshold, enable_query_rewrite,
   min_score_threshold) so config-driven behavior is visible.

Verification:
- `uv run pytest` — all green, including new test_batch23_cli_wiring.py
- `uv run rdos --help` lists `thread`
- `uv run rdos thread new` then `rdos thread ask <id> "follow up question"`
  works end-to-end on clawd-research corpus
- `git ls-files | grep '^data/'` returns only .gitkeep files
- `uv run rdos eval all` still PASSes the 8-metric release gate

Do NOT implement: cloud adapter, LLM-as-judge, web UI, plugin sources.

Tag: v0.2.1-trust-runtime-hardened
Commit message must include trailer:
  Constraint: read-only audit by principal engineer found thread CLI unregistered
  Confidence: high
  Scope-risk: narrow
```

---

## Appendix — Source Evidence

### Agent 1 — Batches 1–8 (full PASS)

All 8 foundation batches verified end-to-end:
- Schemas defined AND used at runtime (`schemas/*.py` consumed by `model_router.py`, `privacy_router.py`, `langgraph_runtime.py`, `tools/registry.py`)
- Parser/chunker deterministic (chunk_hash + chunk_id stable across reindex)
- Indexer idempotent with provider-mismatch guardrails
- Hybrid retriever RRF-merged; citation validator wired into langgraph topology
- PrivacyRouter computes 5-source max; hard-blocks enforced
- LocalLlamaCppAdapter OpenAI-compatible with retry-once + StructuredError
- 10-node research_memory_graph runs as langgraph with linear fallback
- JSONL trace store with redaction default ON

### Agent 2 — Batches 9–17 (8 PASS + 1 PARTIAL)

- Real corpus ingestion with 6 presets + incremental + index report
- Real LangGraph StateGraph with thread_id + node-level trace
- ToolRegistry × PermissionGate × CapabilityBoundary enforce all 6 safety checks
- Adversarial eval sets **actually executed** by `rdos eval all` (50/55/42 cases)
- Architecture consistency: 5/5 ModelRouter checks, 5/6 PrivacyRouter (validator dead), 5/5 Citation, 6/6 Tool Safety, 6/6 Eval

### Agent 3 — Batches 18–22 (1 PASS + 4 PARTIAL)

- Batch 18 quality baseline docs: PASS
- Batch 19 HITL: real ApprovalQueue + interrupt/resume but resume swallows errors
- Batch 20 no-answer: framework complete but threshold defaults to 0
- Batch 21 redaction: 8 recognizers + trace redaction wired, but validator dead code, no cloud adapter
- Batch 22 thread: ThreadStore + rewriter work but `rdos thread` CLI unregistered + carry-forward not wired

**Scoring rationale**: code quality is high (4–5/5 in most areas), but v0.2 readiness is undermined by the thread CLI gap (2/5 real runtime readiness).
