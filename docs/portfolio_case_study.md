# Portfolio Case Study — Personal R&D Agent OS

> **For**: technical interview / portfolio review
> **Project**: `personal-rd-agent-os` (RDOS)
> **Tag**: `v1.0.0`
> **Repo size**: ~12k lines of Python, 230 tests, 24 batches, 3 agent-driven audits

---

## Problem

I have ~2,088 Markdown research notes clipped from the AI/ML literature over 18 months, organized into 25 topic folders (知識與檢索, AI代理系統, LLM推理與評估, AI安全, …). I want to:

1. **Search** them accurately, with Traditional Chinese + English technical terms mixed together.
2. **Trust** the answers — every claim must cite a specific chunk, and the citation must be real (not hallucinated).
3. **Protect** the privacy of the notes — some are private journal entries, some are company-sensitive, none should leak to a cloud model without explicit confirmation.
4. **Trace** every run for forensics — when an answer is wrong, I want to know which chunks fed it and what privacy decision was made.
5. **Evaluate** the system honestly — a release gate decides whether it ships.

Off-the-shelf "local RAG" demos stop at chunk-and-embed. None of them address (2)–(5).

## Design decisions

### 1. Privacy-aware routing — effective privacy is `max`, not `min`

A naive privacy router looks at the query. That misses the case where a `public` query retrieves a `company_sensitive` chunk and then ships both to a cloud model.

**RDOS rule**:

```
effective_privacy = max(
    user_query_privacy,
    retrieved_chunk_privacy_levels,
    tool_result_privacy_level,
    memory_context_privacy_level,
    trace_context_privacy_level,
)
```

`private_raw` and `company_sensitive` **never** reach a cloud model. `private_summary` requires explicit HITL approval. The `PrivacyRouter` lives at `src/rdos/llm/privacy_router.py` and the strictest-wins semantics is tested against adversarial eval cases.

### 2. Citation validation — three-way check

A naive citation system trusts the LLM: whatever `chunk_id` the model emits becomes the citation. That fails when (a) the model invents an ID, (b) the underlying chunk was re-indexed and the hash changed, (c) the model cites a chunk it wasn't shown.

**RDOS rule**: a citation is valid iff

```
chunk_exists ∧ hash_matches ∧ in_retrieved_context
```

Implemented at `src/rdos/rag/citation_validator.py`. Synthesis reports `citation_coverage` — fraction of claims backed by ≥1 valid citation. The AgentTrace synthesis test hits 75% coverage.

### 3. ModelRouter returns data only — never a callable tool-bound model

Most agent frameworks couple "which model" with "what tools" by returning a pre-bound `ChatModel` from the router. That coupling forces the router to know about every tool's privacy eligibility — a layering violation. It also makes the router untestable without mocking the LLM stack.

**RDOS rule**: `ModelRouter.select(...)` returns a `ModelRoutingDecision` Pydantic dataclass. The orchestrator reads it, then constructs the right `LLMAdapter`. Today only `local_fast` (local llama.cpp) and `cloud_reasoning` profiles are wired.

### 4. Tool permission at the boundary, not in tool bodies

Tools shouldn't re-implement path traversal / symlink escape / secret-name checks. The `ToolRegistry.invoke` runs `CapabilityBoundary.check_read` before the tool body. 17 secret patterns (`.env`, `id_rsa`, `credentials`, …) are blocked before any file read.

### 5. Evaluation-driven release

A release gate (RAG recall@5, citation accuracy, model routing correctness, privacy compliance, leakage rate) decides whether the project ships. Two leakage metrics are pinned at zero — any non-zero is automatic FAIL. The gate is deterministic on synthetic data + fake embedding, so CI can run it on every commit.

---

## Architecture summary

```
                        +-----------------+
   .md notes ----index->| MarkdownParser  |
                        +-----------------+
                                |
                                v
                        +-----------------+
                        | Chunker         |
                        +-----------------+
                                |
                  +-------------+-------------+
                  v                           v
        +-----------------+         +-----------------+
        | SQLite          |         | LanceDB         |
        | (metadata, FTS) |         | (vectors)       |
        +-----------------+         +-----------------+
                                |   |
                  +-------------+   |
                  v                 v
        +-----------------+   +-----------------+
        | HybridRetriever|<--| PrivacyRouter   |
        | (RRF merge)    |   +-----------------+
        +-----------------+          |
                  |                  v
                  v          +-----------------+
        +-----------------+ | ModelRouter     |
        | CitationBuilder | | (data only)     |
        +-----------------+ +-----------------+
                  |                  |
                  v                  v
        +-----------------+   +-----------------+
        | CitationValidator  | LLMAdapter      |
        | (3-way check)   |  | (local | cloud) |
        +-----------------+   +-----------------+
                  |                  |
                  v                  v
        +-----------------+   +-----------------+
        | TraceStore      |   | cloud_send shim |
        | (JSONL redacted)|   | (validate_prompt)|
        +-----------------+   +-----------------+
                  |
                  v
        +-----------------+
        | EvalHarness     |
        | (release gate)  |
        +-----------------+
```

**Layers**:
- `src/rdos/rag/` — parser, chunker, indexer, retriever, citation
- `src/rdos/llm/` — provider interface, local llama.cpp adapter, structured output, runtime mode, redaction, cloud_send shim, prompt privacy validator
- `src/rdos/graph/` — LangGraph StateGraph + research_memory_graph + export_graph + checkpointer
- `src/rdos/tools/` — registry, permission gate, capability boundary, safe tools
- `src/rdos/trace/` — JSONL store with redaction-before-write
- `src/rdos/eval/` — release gate, adversarial aggregator, retrieval benchmark, real benchmark, structured output eval, no-answer eval, redaction eval
- `src/rdos/threads/` — multi-turn thread store, follow-up rewriter
- `src/rdos/approvals/` — HITL approval queue with idempotency_key
- `src/rdos/apps/` — digest, topic explorer, synthesize

**Trust boundaries**:
1. **Retrieval boundary** — HybridRetriever returns chunks; effective privacy is computed afterwards
2. **Privacy boundary** — `private_raw` / `company_sensitive` hard-block cloud
3. **Citation boundary** — three-way validator rejects hallucinated / stale / out-of-context citations
4. **Tool boundary** — CapabilityBoundary blocks path traversal / symlink / secrets before tool body
5. **Cloud boundary** — `cloud_send_or_raise()` is the mandatory pre-call hook (no cloud adapter shipped yet, but contract stands)

---

## Privacy routing — concrete

```
query: "整理我關於 AgentTrace 的筆記"
↓
PrivacyRouter.assess_query → private_raw (keyword hint "我的")
↓
HybridRetriever.search → top 5 chunks
  chunk[0]: privacy_level=public
  chunk[1]: privacy_level=private_raw
  chunk[2]: privacy_level=company_sensitive  ← escalates
↓
PrivacyRouter.calculate_effective_privacy:
  effective = max(public, private_raw, company_sensitive)
            = company_sensitive
↓
ModelRouter.select:
  effective=company_sensitive → forced local_fast
  allows_external_model = False
↓
LocalLlamaCppAdapter.generate(...)
↓
CitationBuilder + CitationValidator (3-way check)
↓
TraceStore.append (with redaction)
```

---

## Model routing — concrete

| Task | Privacy | Selected profile | Provider | Confirmation |
| --- | --- | --- | --- | --- |
| research_synthesis | public | cloud_reasoning | cloud | no |
| research_memory | private_raw | local_fast | local | no |
| code_analysis | company_sensitive | local_fast (forced down from code_specialist) | local | no |
| research_synthesis | private_summary | cloud_reasoning | cloud | **yes** (HITL) |

Tested at `tests/test_model_router.py`.

---

## Citation validation — concrete

```python
class CitationValidator:
    def validate(self, citation, retrieved_chunks):
        chunk = self.store.get_chunk(citation.chunk_id)
        chunk_exists = chunk is not None
        hash_matches = bool(chunk) and chunk.chunk_hash == citation.chunk_hash
        retrieved_ids = {c.chunk_id for c in retrieved_chunks}
        in_retrieved = citation.chunk_id in retrieved_ids
        return CitationValidationResult(
            citation=citation,
            chunk_exists=chunk_exists,
            hash_matches=hash_matches,
            in_retrieved_context=in_retrieved,
        )
```

`is_valid = chunk_exists ∧ hash_matches ∧ in_retrieved_context`.

Synthesis reports `citation_coverage = backed_claims / total_claims`. Real run on AgentTrace query: 4 claims, 7 citations, **75% coverage**.

---

## HITL — concrete

```
rdos research synthesize "..." --embedding-provider local-bge-m3
  → synthesis runs
  → export_report wants to write file
  → policy says private_raw requires approval
  → LangGraph interrupt() pauses the thread
  → ApprovalQueue.request() creates idempotency_key = sha256(run_id + tool + args)
  → CLI prints "approval_required"

# Later (hours / days later)
rdos approval list
  → shows pending approval

rdos approval approve <id>
  → ApprovalQueue.decide() marks decision (immutable)
  → LangGraph Command(resume={"decision": "approved"}) rehydrates thread
  → export_report writes the file
  → mark_executed(approval_id) increments replay_count

# Replay attempt
rdos approval approve <id>
  → already decided → no-op (immutable)
```

---

## Eval — concrete

`rdos eval all` prints 4 tables:

1. **Release Gate (foundation regression)** — 8 metrics, deterministic on synthetic data
2. **Adversarial eval (visibility only)** — 3 sets, 50/55/42 cases, actually executed
3. **No-answer gate (opt-in)** — accuracy + false-positive rate
4. **Redaction gate (opt-in)** — recall + precision

Failed cases are listed in `data/reports/eval_report.md` per-eval, truncated to 10 IDs each.

---

## Results

| Metric | Value |
| --- | --- |
| Total tests | 230 passing |
| Release gate | PASS (8/8) |
| Real corpus recall@5 | 0.73 (3 of 25 scopes) |
| Real corpus MRR | 0.69 |
| Real corpus latency p50 | 50 ms |
| Redaction recall / precision | 1.0 / 1.0 |
| Synthesize citation coverage | 75% |
| Audit P0 / P1 findings | 0 / 0 (closed in Batch 18.5 + 23) |

---

## Lessons learned

1. **Fake embedding + fake LLM are first-class citizens.** They keep CI hermetic and let the gate be deterministic. Real model integration is a config swap, not a code change.
2. **Adversarial eval sets are decorative until they're wired into `eval all`.** v0.1 shipped 140+ adversarial cases that were never executed. Batch 18.5 fixed this — always grep for the loader.
3. **LangGraph's default TypedDict reducer is "override", not "merge".** Each node must return the FULL state dict, not a diff. Cost me 5 hours.
4. **Trace redaction default must be ON.** Opt-out for debug; never the other way around.
5. **`git rm --cached` is not enough — `git ls-files` after every batch.** Three runtime files slipped into history before `.gitignore` caught them.
6. **CLI registration is invisible until you check `rdos --help`.** Batch 22's `rdos thread` was unreachable; the test suite passed because tests imported the module directly.
7. **Idempotency keys are cheap insurance.** `sha256(run_id + tool + args)` prevents double-execution of approved tools for free.
8. **Don't write the cloud adapter until you have to.** Local-first design is a feature; cloud is opt-in for `public` / `private_summary` only.

---

## Resume bullet

> Designed and built **Personal R&D Agent OS** — a local-first, model-agnostic, privacy-aware research-memory agent runtime (~12k LOC Python, 230 tests). Indexes 2,088 Markdown research notes via SQLite + LanceDB, retrieves with hybrid semantic+keyword RRF, validates every citation three ways (`chunk_exists ∧ hash_matches ∧ in_retrieved_context`), routes through effective-privacy-aware model selection (`max` across query + retrieved chunks + tool results + memory + trace), enforces tool permission via `PermissionGate × CapabilityBoundary` (blocks path traversal / symlink escape / 17 secret-name patterns), writes redacted JSONL trace on every run, and ships with an 8-metric release gate plus 147 adversarial eval cases. Tagged `v1.0.0` after 3-agent parallel audit closed all P0/P1 findings.
