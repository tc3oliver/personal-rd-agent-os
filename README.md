# Personal R&D Agent OS

RDOS is a **local-first, privacy-aware, model-agnostic personal R&D agent runtime** that turns a real research note corpus into searchable, citation-grounded, traceable, and evaluation-driven research workflows.

> Status: **v1.0.1 maintenance-only**
> v1.0.0 is feature complete. v1.0.1 contains a post-release validation fix. No new feature work is planned for v1.x.

---

## What This Is

Personal R&D Agent OS, or RDOS, is not a chatbot.

It is a personal AI engineering system designed to support long-term research work:

```text
Markdown notes
→ index
→ retrieve
→ cite
→ privacy route
→ model route
→ generate
→ structure
→ validate
→ trace
→ evaluate
→ research workflows
```

RDOS is built around one core idea:

> A personal research assistant should not only answer questions.
> It should know where the answer came from, whether it is allowed to use the data, which model was selected, what tools were used, and how the result was evaluated.

---

## Core Capabilities

RDOS v1.0 includes:

* Local Markdown research corpus ingestion
* Local embedding with `bge-m3-q8_0`
* Local LLM runtime with `qwythos-9b-q4`
* Hybrid retrieval with semantic + keyword search
* Citation-grounded answers
* Citation validation
* Privacy-aware model routing
* Model-agnostic runtime design
* LangGraph StateGraph execution
* HITL approval runtime
* Runtime tool permission gate
* Capability boundary for safe file tools
* No-answer calibration framework
* Redaction guardrails
* Multi-turn research threads
* JSONL trace store
* Evaluation and benchmark release gates
* Research apps:

  * ask
  * digest
  * topic explorer
  * synthesis

---

## Why This Project Exists

Most personal AI knowledge tools stop at:

```text
notes → vector search → chatbot answer
```

RDOS focuses on the missing engineering layer:

```text
retrieval quality
citation validity
privacy boundary
model routing
tool permission
approval flow
runtime trace
evaluation gate
```

The goal is to make personal research workflows:

* searchable
* explainable
* privacy-aware
* locally runnable
* traceable
* measurable
* maintainable

---

## Architecture Overview

```text
RDOS
│
├── CLI
│   ├── index
│   ├── index-corpus
│   ├── search
│   ├── ask
│   ├── thread
│   ├── research
│   ├── approval
│   ├── trace
│   ├── eval
│   ├── benchmark
│   ├── doctor
│   └── tool
│
├── Runtime
│   ├── LangGraph StateGraph
│   ├── Thread state
│   ├── HITL approval
│   ├── Privacy router
│   ├── Model router
│   ├── Tool permission gate
│   └── Trace logger
│
├── Retrieval
│   ├── Markdown parser
│   ├── Heading-aware chunker
│   ├── SQLite metadata store
│   ├── LanceDB vector store
│   ├── Local bge-m3 embeddings
│   ├── Hybrid search
│   ├── Query rewrite
│   └── Citation builder / validator
│
├── Model Layer
│   ├── Stub adapter
│   ├── Local llama.cpp-compatible chat adapter
│   ├── Local OpenAI-compatible embedding adapter
│   └── Runtime mode resolver
│
├── Trust Runtime
│   ├── Effective privacy calculation
│   ├── Model routing decision
│   ├── Permission boundary
│   ├── Approval queue
│   ├── Redaction guardrails
│   ├── No-answer handling
│   └── Eval gates
│
└── Research Apps
    ├── Research ask
    ├── Digest
    ├── Topic explorer
    ├── Synthesis
    └── Multi-turn research thread
```

---

## Trust Boundaries

RDOS explicitly separates five trust boundaries.

### 1. Data Boundary

Private research notes stay local by default.

```text
public < private_summary < private_raw < company_sensitive
```

Effective privacy is calculated across all sources:

```text
effective_privacy = max(
  user_query_privacy,
  retrieved_chunk_privacy,
  tool_result_privacy,
  memory_context_privacy,
  trace_context_privacy
)
```

### 2. Model Boundary

The model router returns a routing decision, not a bound model.

This avoids coupling privacy decisions, tool access, and model adapter behavior.

```text
ModelRouter → ModelRoutingDecision
Workflow node → selects runtime adapter
Tool layer → binds or blocks tools separately
```

### 3. Retrieval Boundary

Every citation must map back to indexed chunks.

Citation validation checks:

* chunk exists
* chunk hash matches
* citation came from retrieved context
* stale chunks are detected
* unsupported claims are flagged

### 4. Tool Boundary

Tools are not executed just because a model asks for them.

Tool execution goes through:

```text
tool request
→ permission gate
→ capability boundary
→ approval decision
→ execution
→ trace
```

Safe file tools enforce:

* allowed roots
* blocked secret patterns
* path traversal prevention
* symlink escape prevention
* max file size

### 5. Execution Boundary

Every workflow is traceable.

Trace records include:

* run ID
* thread ID
* graph runtime
* model routing decision
* privacy decision
* retrieved chunks
* citations
* permission decisions
* approval decisions
* final output
* metrics
* errors

---

## Local Model Stack

RDOS v1.0 was validated with the following local model stack:

| Purpose          | Endpoint                     | Model           |
| ---------------- | ---------------------------- | --------------- |
| Chat / reasoning | `http://10.10.10.12:8080/v1` | `qwythos-9b-q4` |
| Embedding        | `http://10.10.10.12:8081/v1` | `bge-m3-q8_0`   |

The local embedding model outputs 1024-dimensional vectors.

Runtime modes:

```text
stub   → always use StubLLMAdapter
local  → require real local LLM; fail if unavailable
auto   → prefer local LLM; fallback to stub with warning
```

---

## Installation

```bash
git clone <repo-url>
cd personal-rd-agent-os

uv sync
```

Check the CLI:

```bash
uv run rdos --help
```

Run tests:

```bash
uv run pytest
uv run ruff check .
```

---

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Example local model settings:

```env
RDOS_LOCAL_CHAT_BASE_URL=http://10.10.10.12:8080/v1
RDOS_LOCAL_CHAT_MODEL=qwythos-9b-q4

RDOS_LOCAL_EMBEDDING_BASE_URL=http://10.10.10.12:8081/v1
RDOS_LOCAL_EMBEDDING_MODEL=bge-m3-q8_0
RDOS_LOCAL_EMBEDDING_DIM=1024

RDOS_LOCAL_MODEL_API_KEY=local-dev-key
```

Check local model health:

```bash
uv run rdos doctor models
```

Expected checks:

```text
chat health
chat generate
embedding health
embedding dim = 1024
embedding batch
```

---

## Quickstart

### 1. Index sample notes

```bash
uv run rdos index ./sample_data/notes --embedding-provider fake
```

### 2. Search

```bash
uv run rdos search "RAG filtering" --embedding-provider fake
```

### 3. Ask

```bash
uv run rdos ask "RAG filtering 是什麼？" \
  --embedding-provider fake \
  --llm-mode stub
```

### 4. Show trace

```bash
uv run rdos trace list
uv run rdos trace show <run_id>
```

### 5. Run evaluation

```bash
uv run rdos eval all
```

---

## Real Corpus Usage

RDOS can ingest a real personal research corpus such as:

```text
~/Workspace/notes/AI/clawd-research/
```

Example:

```bash
uv run rdos index-corpus clawd-research \
  --scope rag \
  --embedding-provider local-bge-m3
```

Supported corpus scopes:

```text
rag       → 知識與檢索
agent     → AI代理系統
eval      → LLM推理與評估
security  → AI安全
devtools  → 開發者工具與框架
all       → all configured folders
```

Search real corpus:

```bash
uv run rdos search "GraphRAG VectorRAG 層次化摘要" \
  --embedding-provider local-bge-m3
```

Ask against real corpus:

```bash
uv run rdos ask "我有沒有整理過 AgentTrace？" \
  --embedding-provider local-bge-m3 \
  --llm-mode local
```

---

## Research Workflows

### Research Ask

```bash
uv run rdos ask "我有沒有整理過 AgentTrace？" \
  --embedding-provider local-bge-m3 \
  --llm-mode local
```

### Digest

```bash
uv run rdos research digest \
  --since 2026-07-01 \
  --collection clawd-research \
  --embedding-provider local-bge-m3 \
  --llm-mode local
```

### Topic Explorer

```bash
uv run rdos research topic "AgentTrace" \
  --collection clawd-research \
  --embedding-provider local-bge-m3 \
  --llm-mode local
```

### Synthesis

```bash
uv run rdos research synthesize \
  "整理我關於 AgentTrace 與 agent flight recorder 的筆記" \
  --collection clawd-research \
  --embedding-provider local-bge-m3 \
  --llm-mode local
```

### Multi-turn Research Thread

```bash
uv run rdos thread new "AgentTrace RDOS trace design"

uv run rdos thread ask <thread_id> \
  "我有沒有整理過 AgentTrace 或 agent flight recorder 相關資料？" \
  --embedding-provider local-bge-m3 \
  --llm-mode local

uv run rdos thread ask <thread_id> \
  "這些資料對 RDOS 的 trace design 有什麼啟發？" \
  --embedding-provider local-bge-m3 \
  --llm-mode local

uv run rdos thread show <thread_id>
uv run rdos thread close <thread_id>
```

---

## HITL Approval Runtime

RDOS supports approval-required tool execution.

Example flow:

```text
research synthesize
→ export_report requires approval
→ approval request created
→ approval list/show
→ approval approve
→ resume
→ markdown file written
```

Approval commands:

```bash
uv run rdos approval list
uv run rdos approval show <approval_id>
uv run rdos approval approve <approval_id>
uv run rdos approval deny <approval_id>
```

The approval runtime is designed for tools that produce side effects, such as exporting reports.

Dangerous tools are intentionally out of scope:

```text
run_shell
git_push
send_email
delete_file
```

---

## Tool Permission Runtime

List tools:

```bash
uv run rdos tool list
```

Read a note through the permission boundary:

```bash
uv run rdos tool read-note sample_data/notes/rag_filtering.md
```

Blocked secret example:

```bash
uv run rdos tool read-note .env
```

Policy check:

```bash
uv run rdos tool policy-check export_report --privacy private_raw
```

The runtime blocks:

* `.env`
* private keys
* credentials
* path traversal
* symlink escape
* oversized files
* disallowed roots

---

## Evaluation

Run deterministic regression gate:

```bash
uv run rdos eval all
```

Foundation gate metrics:

| Metric                          |  Target |
| ------------------------------- | ------: |
| RAG Recall@5                    | >= 0.75 |
| Citation Accuracy               | >= 0.70 |
| Valid Chunk Reference Rate      | >= 0.95 |
| Structured Output JSON Validity | >= 0.95 |
| Model Routing Correct Rate      | >= 0.85 |
| Privacy Policy Compliance       |  = 1.00 |
| Private Raw Leakage Rate        |     = 0 |
| Company-sensitive Leakage Rate  |     = 0 |

Run adversarial evaluation:

```bash
uv run rdos eval adversarial
```

Run benchmark:

```bash
uv run rdos benchmark all
```

---

## v1.0 Quality Baseline

### Foundation Regression Gate

Status: **PASS**

The deterministic regression gate is designed to run on every commit using controlled sample data.

### Real Corpus Benchmark

Validated on selected real corpus scopes:

```text
rag / agent / eval
```

Current benchmark:

| Metric                      | Value |
| --------------------------- | ----: |
| Recall@5                    |  0.73 |
| MRR                         |  0.69 |
| Retrieval latency p50       | 50 ms |
| Synthesis citation coverage |   75% |

This is a quality baseline, not a claim of final retrieval quality over the entire corpus.

---

## Post-release Validation

After v1.0.0, two real-runtime validation flows were executed.

### Validation A: HITL Approval Lifecycle

Real-tested with:

```text
local-bge-m3 + qwythos
```

Flow:

```text
synthesize
→ approval_required
→ approve
→ resume
→ markdown report written
```

Result:

```text
PASS
```

One blocking bug was found and fixed in the HITL export resume path.

### Validation B: Multi-turn Research Thread

Real-tested with:

```text
local-bge-m3 + qwythos
```

Flow:

```text
thread new
→ thread ask × 3
→ cited context carry-forward
→ thread show
→ thread close
```

Result:

```text
PASS
```

The real multi-turn validation completed 3 turns with cited carry-forward.

---

## Demo Scripts

```bash
bash scripts/demo_v1_foundation.sh
bash scripts/demo_v1_trust_runtime.sh
bash scripts/demo_v1_research_thread.sh
bash scripts/demo_v1_eval.sh
```

---

## Repository Structure

```text
personal-rd-agent-os/
├── configs/
│   ├── models.yaml
│   ├── privacy_policy.yaml
│   ├── rag.yaml
│   └── tool_policy.yaml
│
├── docs/
│   ├── final_architecture.md
│   ├── portfolio_case_study.md
│   ├── project_closeout.md
│   ├── limitations.md
│   ├── parking_lot.md
│   ├── quality_baseline_v0.1.0.md
│   ├── release_notes/
│   └── validation/
│
├── src/rdos/
│   ├── apps/
│   ├── cli/
│   ├── eval/
│   ├── graph/
│   ├── llm/
│   ├── rag/
│   ├── schemas/
│   ├── tools/
│   └── trace/
│
├── eval_sets/
├── sample_data/
├── scripts/
├── tests/
└── data/
```

---

## What Is Real in v1.0

Implemented and validated:

* real local embedding with `bge-m3-q8_0`
* real local LLM with `qwythos-9b-q4`
* real corpus ingestion
* selected real corpus benchmark
* LangGraph StateGraph runtime
* thread ID and trace integration
* runtime tool permission gate
* HITL approval lifecycle
* real multi-turn research thread
* citation validation
* JSONL trace
* adversarial eval sets
* digest / topic / synthesis apps

---

## Known Limitations

RDOS v1.0 is feature complete, but it is not a production-grade multi-user agent platform.

Known limitations:

* No production cloud adapter
* Cloud escalation uses guardrails / shim behavior
* No LLM-as-judge answer quality grading
* No-answer threshold defaults to conservative behavior and should be calibrated per corpus before aggressive use
* Default checkpointer is still local/dev oriented
* Only selected corpus scopes were benchmarked
* No Web UI expansion
* No external source plugins
* No multi-tenant deployment model

---

## Intentionally Out of Scope

The following are intentionally parked and are not planned for v1.x:

* GitHub integration
* arXiv integration
* Hacker News / RSS plugins
* Web UI expansion
* Mobile app
* Browser extension
* Auto code editing
* IDE integration
* Production multi-user deployment
* Knowledge graph rewrite
* Plugin marketplace

Dangerous tools are permanently out of scope:

```text
run_shell
git_push
send_email
delete_file
```

---

## Maintenance Policy

After v1.0.1, this repository is in maintenance-only mode.

Allowed:

* bug fixes
* dependency updates
* documentation corrections
* security patches
* eval/report corrections

Not allowed in v1.x:

* new apps
* new connectors
* Web UI expansion
* architecture rewrites
* auto code editing
* production multi-user deployment
* knowledge graph rewrite

Future feature ideas should be written to:

```text
docs/parking_lot.md
```

They should not be implemented in this repository.

---

## Release Tags

```text
v0.1.0-foundation
v0.2.0-trust-runtime
v0.2.1-trust-runtime-hardened
v1.0.0
v1.0.1
```

---

## Portfolio Summary

RDOS demonstrates practical AI engineering beyond a chatbot or RAG demo.

Key engineering themes:

* model-agnostic runtime design
* local-first privacy boundary
* citation-grounded retrieval
* structured output validation
* runtime tool permission
* HITL approval
* traceability
* eval-driven iteration
* adversarial testing
* release discipline
* feature freeze and maintenance policy

Resume bullet:

```text
Built RDOS, a local-first, privacy-aware, model-agnostic personal R&D agent runtime using LangGraph, local bge-m3 embeddings, a local qwythos LLM, hybrid retrieval, citation validation, privacy/model routing, HITL approval, no-answer calibration, redaction guardrails, multi-turn research threads, JSONL tracing, and eval/benchmark release gates. The system indexes a real personal AI research corpus and supports research Q&A, digests, topic exploration, and synthesis workflows, validated with adversarial evals, real-runtime validation, traceability, and runtime tool permission boundaries.
```

---

## Final Status

```text
RDOS v1.0.1 is complete.

Feature development is frozen.
The project is now maintenance-only.
```
