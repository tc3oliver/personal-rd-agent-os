# Final Architecture — RDOS v1.0

> Single source of truth for v1.0 architecture. Companion to [docs/architecture.md](./architecture.md) (full v1 spec) and [docs/architecture_overview.md](./architecture_overview.md) (high-level).

## Modules

```
src/rdos/
├── cli/                 Typer entry points (14 subcommands)
│   ├── __init__.py      Registers all sub-apps
│   ├── ask.py           rdos ask — research_memory_graph entry
│   ├── approval.py      rdos approval list/show/approve/deny
│   ├── benchmark.py     rdos benchmark retrieval/all
│   ├── corpus.py        rdos index-corpus (6 presets)
│   ├── doctor.py        rdos doctor models
│   ├── eval.py          rdos eval all + opt-in subcommands
│   ├── index.py         rdos index
│   ├── redaction.py     rdos redaction scan/eval
│   ├── research_apps.py rdos research digest/topic/synthesize
│   ├── search.py        rdos search
│   ├── thread.py        rdos thread new/ask/list/show/close
│   ├── tool.py          rdos tool read-note/policy-check/list/search
│   └── trace.py         rdos trace list/show
├── schemas/             Pydantic data contracts
│   ├── citation.py      Citation, CitationValidationResult, CitationReport
│   ├── document.py      DocumentMetadata, DocumentChunk
│   ├── privacy.py       PrivacyLevel, PrivacyDecision, privacy_max
│   ├── research.py      ResearchAnswer
│   ├── research_apps.py DigestOutput, TopicExplorerOutput, SynthesisOutput
│   ├── routing.py       ModelRoutingDecision
│   └── trace.py         TraceRecord, TraceMetrics, TraceError
├── rag/                 Retrieval-Augmented Generation layer
│   ├── chunker.py       heading-aware chunker with chunk_hash dedup
│   ├── citation_builder.py  query-relevant quote selection
│   ├── citation_validator.py  3-way validation
│   ├── corpus_presets.py  6 corpus scopes (rag/agent/eval/security/devtools/all)
│   ├── embedding.py     FakeEmbeddingProvider + OpenAICompatibleEmbeddingProvider
│   ├── hybrid_search.py RRF + RetrievalFilters
│   ├── indexer.py       incremental index with stale marking
│   ├── markdown_parser.py  frontmatter + heading tree + fallbacks
│   ├── query_rewriter.py  English-term + CJK n-gram + alias expansion
│   ├── retriever.py     HybridRetriever (semantic + keyword + RRF + no-answer)
│   ├── storage_sqlite.py  SQLite documents + chunks + FTS
│   └── vector_store.py  LanceDB with provider metadata + mismatch guards
├── llm/                 LLM provider + structured output + privacy
│   ├── cloud_send.py    MANDATORY pre-call hook for any future cloud adapter
│   ├── local_llama_cpp.py  OpenAI-compatible adapter (qwythos-9b-q4)
│   ├── model_router.py  Returns ModelRoutingDecision (data only)
│   ├── privacy_router.py  Effective privacy = max across 5 sources
│   ├── prompt_privacy_validator.py  Last-line-of-defense (PII / company hint)
│   ├── provider.py      LLMAdapter Protocol + StubLLMAdapter + LLMMessage
│   ├── redaction.py     8 recognizers (EMAIL/PHONE_TW/ID_TW/URL/IP/CREDIT_CARD/ADDRESS_TW/COMPANY_HINT)
│   ├── runtime_mode.py  stub|local|auto resolver
│   └── structured_output.py  Pydantic + retry once + StructuredError
├── graph/               LangGraph runtime
│   ├── checkpointer.py  SQLite checkpointer factory (InMemorySaver is default)
│   ├── export_graph.py  HITL approval workflow (synthesize → interrupt → resume)
│   ├── langgraph_runtime.py  StateGraph with 10 nodes + node-level trace
│   ├── research_memory_graph.py  Linear runner (legacy fallback)
│   ├── root_graph.py    Task dispatcher
│   └── state.py         ResearchGraphState TypedDict
├── tools/               Tool permission + safe tools
│   ├── capability_boundary.py  Path traversal / symlink / secrets / max_bytes
│   ├── export_tools.py  ExportReportTool (requires_approval)
│   ├── knowledge_tools.py  SearchNotes / ReadNote / ListRecentNotes
│   ├── permission_gate.py  Privacy-aware allow/deny/confirm matrix
│   └── registry.py      ToolRegistry
├── trace/               JSONL trace store
│   ├── trace_logger.py  Timer + new_run_id + record_run
│   └── trace_store.py   JsonlTraceStore (redact=True default) + build_record_from_state
├── eval/                Eval harness
│   ├── adversarial.py   Aggregator for *_adversarial.jsonl
│   ├── citation_eval.py
│   ├── model_routing_eval.py
│   ├── no_answer_calibrate.py
│   ├── no_answer_eval.py
│   ├── privacy_eval.py
│   ├── rag_eval.py
│   ├── real_benchmark.py
│   ├── redaction_eval.py
│   ├── report.py        RELEASE_GATE / NO_ANSWER_GATE / REDACTION_GATE
│   ├── retrieval_benchmark.py
│   └── structured_output_eval.py
├── threads/             Multi-turn research thread
│   ├── models.py        ThreadState + TurnRecord
│   ├── rewriter.py      Pronoun/deixis resolution + carry-forward + compression
│   └── store.py         SQLite-backed ThreadStore
├── approvals/           HITL approval queue
│   ├── models.py        ApprovalRequest
│   └── queue.py         ApprovalQueue with idempotency_key + replay protection
├── apps/                Research apps
│   ├── digest.py        Daily Digest
│   ├── synthesize.py    Citation-grounded synthesis with coverage metric
│   └── topic.py         Topic Explorer
└── config.py            YAML loader with env substitution
```

## Data flow

```
[Markdown notes on disk]
    │
    ▼ rdos index / rdos index-corpus
[SQLite: documents + chunks + FTS]   [LanceDB: vectors + provider metadata]
    │                                       │
    └──────────────┬────────────────────────┘
                   │
                   ▼ rdos ask / rdos thread ask / rdos research synthesize
    [HybridRetriever]
         │  ↓ semantic (LanceDB cosine)
         │  ↓ keyword (SQLite FTS)
         │  ↓ RRF merge
         │  ↓ no-answer check (if threshold > 0)
         ▼
    [PrivacyRouter: effective = max(query, chunks, tools, memory, trace)]
         │
         ▼
    [ModelRouter: data-only decision (profile, provider, allows_external)]
         │
         ▼
    [LLMAdapter (local_fast | cloud_reasoning | code_specialist)]
         │  ↑ cloud_send_or_raise() called IF external
         ▼
    [CitationBuilder + CitationValidator: 3-way check]
         │
         ▼
    [StructuredOutput: Pydantic + retry once + StructuredError]
         │
         ▼
    [TraceStore: JSONL with redaction-before-write]
         │
         ▼
    [EvalHarness: 8-metric release gate + adversarial + opt-in gates]
```

## Trust boundaries (5 layers)

1. **Retrieval boundary** — `HybridRetriever` returns chunks; `RetrievalFilters` enforce privacy / tags / folder / date
2. **Privacy boundary** — `PrivacyRouter.calculate_effective_privacy` strictest-wins; `private_raw` / `company_sensitive` hard-block external
3. **Citation boundary** — `CitationValidator.validate` enforces `chunk_exists ∧ hash_matches ∧ in_retrieved_context`
4. **Tool boundary** — `CapabilityBoundary.check_read` runs before tool body; 17 secret-name patterns blocked
5. **Cloud boundary** — `cloud_send_or_raise()` is the mandatory pre-call hook for any future cloud adapter (validator + recognizers)

## Runtime flow (LangGraph)

```
START
  ↓
classify_task
  ↓
assess_query_privacy
  ↓
retrieve_notes
  ↓
calculate_effective_privacy
  ↓
select_model_profile
  ↓
build_context
  ↓
generate_answer
  ↓
build_citations
  ↓
validate_citations
  ↓
format_structured_output
  ↓
END
```

Each node records `name / status / latency_ms / inputs_summary / outputs_summary` into node-level trace. Thread_id is uuid4 hex per invoke.

## HITL flow (export_graph)

```
START
  ↓
synthesize
  ↓
request_approval → interrupt() pauses thread
  ↓                   ↓
  │             [ApprovalQueue.request creates idempotency_key]
  │
  │   [later: rdos approval approve <id>]
  │            ↓
  │       ApprovalQueue.decide (immutable)
  │            ↓
  │       Command(resume={"decision": "approved"})
  ↓
write_or_skip
  ↓  ↓ approved → write file, mark_executed
  ↓  ↓ denied   → skip, record reason
  ↓  ↓ replay   → mark_executed, no double-write
END
```

## Eval flow

```
rdos eval all
  ↓
evaluate_rag              (sample_data + fake)
evaluate_citation         (sample_data + fake)
evaluate_model_routing    (sample_data + fake)
evaluate_privacy          (sample_data + fake)
evaluate_structured_output (JSON round-trip)
  ↓
evaluate_citation_adversarial   (42 cases)
evaluate_model_routing_adversarial (55 cases)
evaluate_privacy_adversarial    (50 cases)
  ↓
evaluate_no_answer        (30 cases + false-positive check)
evaluate_redaction        (10 built-in samples)
  ↓
write_report → data/reports/eval_report.md
  ↓
print 4 tables: Release Gate / Adversarial / No-answer gate / Redaction gate
```

## Storage

| Store | Path | Purpose |
| --- | --- | --- |
| SQLite metadata | `data/sqlite/rdos.db` | documents, chunks, FTS keyword |
| LanceDB vectors | `data/lancedb/` | chunk embeddings + provider metadata |
| JSONL trace | `data/traces/runs.jsonl` | one self-contained record per run |
| Approval queue | `data/approvals.db` | HITL approval decisions |
| LangGraph checkpoint | `data/checkpoints.db` | (used by export_graph) |
| Thread store | `data/threads.db` | Multi-turn thread state |
| Index reports | `data/reports/index_report_*.md` | per-indexing audit trail |
| Eval report | `data/reports/eval_report.md` | per-eval failure list |
| Benchmark report | `data/reports/benchmark_report.md` | retrieval + ask latency |
| Generated apps output | `data/generated/{digests,topics,reports}/` | research app outputs |

All `data/` runtime outputs are gitignored (Batch 23 hygiene fix).
