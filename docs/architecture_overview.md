# Architecture Overview

RDOS is a personal R&D agent that turns Markdown notes into a queryable, citable, traceable knowledge base with privacy-aware model routing.

This document is a high-level companion to [architecture.md](./architecture.md) (the full v1 spec) and [batches/](./batches/) (the per-batch build plan). For per-component design rationale, see the case studies under [case_studies/](./case_studies/).

## Component map

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
                  |                           |
                  v                           v
        +-----------------+         +-----------------+
        | SQLite          |         | LanceDB         |
        | (metadata, FTS) |         | (vectors)       |
        +-----------------+         +-----------------+
                  ^                           ^
                  |                           |
                  +-------------+-------------+
                                |
                                v
                        +-----------------+
                        | HybridRetriever |  (RRF merge)
                        +-----------------+
                                |
                                v
                  +-------------+-------------+
                  | PrivacyRouter             |
                  | effective = max across    |
                  | query / chunks / tools /  |
                  | memory / trace            |
                  +-------------+-------------+
                                |
                                v
                        +-----------------+
                        | ModelRouter     |  (data only, no bound tools)
                        +-----------------+
                                |
                                v
                        +-----------------+
                        | LLMAdapter      |  (local llama.cpp | stub | cloud)
                        +-----------------+
                                |
                                v
                        +-----------------+
                        | Structured      |  (Pydantic + retry once)
                        | Output          |
                        +-----------------+
                                |
                                v
                  +-------------+-------------+
                  | CitationValidator         |
                  | (chunk_exists ∧           |
                  |  hash_matches ∧           |
                  |  in_retrieved_context)    |
                  +-------------+-------------+
                                |
                                v
                        +-----------------+
                        | TraceStore      |  (JSONL append)
                        +-----------------+
                                |
                                v
                        +-----------------+
                        | EvalHarness     |  (release gate)
                        +-----------------+
```

## Data contracts

Pydantic schemas live in `src/rdos/schemas/`. The seven load-bearing ones:

| Schema | Why it exists |
| --- | --- |
| `DocumentChunk` | Heading-aware chunk with stable `chunk_hash` for idempotent indexing |
| `Citation` | Reference from answer back to a source chunk |
| `CitationValidationResult` | Three-way check: exists ∧ hash matches ∧ in retrieved context |
| `PrivacyDecision` | Carries every input source plus the final effective level |
| `ModelRoutingDecision` | Pure-data routing result; no callable model embedded |
| `ResearchAnswer` | Final user-facing answer + citations + confidence + routing provenance |
| `TraceRecord` | Self-contained JSONL record of one run |

## Routing pipeline

1. **Classify** the user query into a `task_type` (only `research_memory` today).
2. **Assess query privacy** via keyword hints from `configs/privacy_policy.yaml`.
3. **Retrieve** candidate chunks with hybrid (semantic + keyword) search.
4. **Compute effective privacy** as `max(query, chunks, tools, memory, trace)`.
5. **Select model profile** from `configs/models.yaml`, force-downgrading cloud choices if privacy demands local.
6. **Generate** with the chosen adapter (or stub for offline dev).
7. **Build + validate citations** against the store and retrieved context.
8. **Format structured output** (Pydantic, retry once, structured error on failure).
9. **Trace** the run to JSONL.

## Storage layout

- **SQLite** (`data/sqlite/rdos.db`) — document metadata, chunk metadata, FTS keyword table. Source of truth for chunk existence.
- **LanceDB** (`data/lancedb`) — chunk embeddings keyed by `chunk_hash` so re-index is a no-op.
- **Traces** (`data/traces/runs.jsonl`) — one JSONL line per run, append-only.

## Configuration

YAML in `configs/`, env-substituted (`${VAR}` syntax):

- `models.yaml` — model profiles, task defaults, embedding provider
- `privacy_policy.yaml` — privacy order, per-level rules, query hint keywords
- `rag.yaml` — chunking targets, retrieval weights, storage paths
- `tool_policy.yaml` — placeholder for tool permission gating

## What's intentionally deferred

- **LangGraph StateGraph migration** — Batch 7 ships a linear runner; porting to a real StateGraph with checkpoints waits until resume / interrupt UX firms up.
- **Real embeddings** — FakeEmbeddingProvider is the default. Swap to local `bge-m3-q8_0` (1024-d) by flipping `configs/models.yaml` once retrieval is stable on real data.
- **Tool calling** — `configs/tool_policy.yaml` exists; the runtime gate lands later.
- **Multi-turn conversations** — current graph is single-shot per query.

## Testing strategy

- **Unit tests** for every module (parser, chunker, stores, retriever, routers, structured output, trace).
- **Integration tests** for the full 11-node research_memory_graph against synthetic notes.
- **Eval harness** with 4 fixtures covering RAG recall, citation accuracy, model routing correctness, and privacy compliance/leakage.

All tests run offline — `StubLLMAdapter` and `FakeEmbeddingProvider` keep CI hermetic.
