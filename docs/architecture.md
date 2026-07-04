# Personal R&D Agent OS v1 Final Architecture Spec

> 專案定位：模型無關的個人研發 Agent 作業系統
> Repo 建議：`personal-rd-agent-os`
> CLI 建議：`rdos`
> 技術主軸：LangChain v1 / LangGraph v1 / Model Router / RAG / Tool Permission / Structured Output / Trace / Eval
> 核心原則：Local-first, model-agnostic, privacy-aware, evaluation-driven
> 文件版本：v1 Final Architecture Spec
> 日期：2026-07-04

---

## 0. Executive Summary

Personal R&D Agent OS 是一套模型無關的個人研發 Agent 作業系統，目標是把個人研究筆記、技術資料、工作思考、工程分析、寫作流程與專案規劃，整合成一套可查詢、可執行、可追蹤、可評估、可持續優化的 AI 系統。

本專案不是本地模型 demo，也不是單純 RAG chatbot。它的核心價值不在於某一顆模型，而在於建立一套可長期升級的 Agentic R&D workflow。

本系統採用 LangChain v1 + LangGraph v1 作為核心架構。LangChain 負責 model integration、tools、middleware、structured output、agent components 等應用層抽象；LangGraph 作為 orchestration runtime，負責 StateGraph workflow、checkpoint-based persistence、streaming、human-in-the-loop、interrupt / resume 與 stateful workflow。LangChain v1 的 agent 支援 `create_agent`、tools、middleware 與 structured output；LangGraph 則提供 graph state checkpointing、thread-based persistence 與 interrupt/resume 機制，適合本專案的多步狀態、人工審核、工具權限與 trace 需求。

本地 `qwythos-9b-q4` 只作為 `local_fast` model profile，用於低成本、低風險、可重試的任務，例如簡短摘要、metadata extraction、低風險 RAG、JSON formatter、daily digest draft。高推理、多文件綜合、長上下文、程式碼分析、架構分析、履歷文件與工作提案，則透過 Model Router 切換到 `cloud_reasoning`、`long_context` 或 `code_specialist` profile。

本專案的最終價值是：

```text
Personal R&D Agent OS
= Research Memory
+ Research Synthesis
+ Daily Digest
+ Topic Explorer
+ Technical Writing
+ Project Planning
+ Engineering Analysis
+ Model Routing
+ Privacy Routing
+ Tool Permission
+ Structured Output
+ Trace
+ Evaluation
```

對履歷而言，本專案可以展示完整 AI engineering 能力：

1. LangChain v1 / LangGraph v1 agent system design
2. Model-agnostic LLM application architecture
3. Local + cloud hybrid model routing
4. Citation-grounded RAG
5. Privacy-aware retrieval and model routing
6. Structured output and schema validation
7. Permission-gated tool execution
8. Human-in-the-loop workflow
9. Trace logging and observability
10. Evaluation-driven optimization
11. Local-first personal knowledge infrastructure
12. Agent workflow regression testing

---

## 1. Project Definition

### 1.1 Project Name

```text
Personal R&D Agent OS
```

建議 Repo：

```text
personal-rd-agent-os
```

建議 CLI：

```text
rdos
```

此處的 OS 指的是「個人研發工作的操作層」，不是作業系統核心。

```text
OS = operating layer for personal R&D workflows
```

---

### 1.2 一句話定位

Personal R&D Agent OS 是一套以 LangChain / LangGraph 為核心的模型無關 Agent 平台，整合本地模型、雲端模型、個人研究筆記、工程文件、RAG、工具調用、structured output、trace 與 eval，讓個人的研究與工程工作流變成可查詢、可執行、可追蹤、可持續優化的 AI 系統。

---

### 1.3 專案不是什麼

本專案不是：

1. local chatbot
2. 單純 RAG demo
3. 只服務某個小模型的 app
4. Obsidian 搜尋插件
5. 自動 code review bot
6. auto-commit coding agent
7. 只為了跑 llama.cpp 的測試專案
8. 沒有 eval 的展示型 demo
9. 沒有 trace 的黑盒 agent
10. 把所有任務都丟給單一 ReAct agent 的 wrapper

---

### 1.4 專案是什麼

本專案是：

1. 個人研究記憶系統
2. 個人技術資料 RAG 系統
3. 個人技術寫作與提案輔助系統
4. 個人工作規劃與決策輔助系統
5. 模型無關的 Agent Runtime
6. 隱私感知的本地優先 AI workflow
7. 可追蹤、可評估、可持續優化的 AI engineering side project
8. 可放履歷與 GitHub 的完整技術作品
9. 可反哺工作上 AI Agent / AI Platform / RAG / Eval 經驗的實驗場
10. 以 eval gate 驅動品質提升的個人 AI engineering platform

---

## 2. Design Principles

### 2.1 Model-agnostic

產品能力不由單一模型決定。

錯誤設計：

```text
我有一顆 9B Q4 本地模型，所以系統只能做小模型能做的事情。
```

正確設計：

```text
我要建立 Personal R&D Agent OS。
簡單、低風險、低成本任務交給本地模型。
深度推理、長文件、程式碼、寫作與重要分析交給更強模型。
所有模型結果都進 trace / eval / feedback loop。
```

Model Router 是本專案的核心能力，不是附加功能。

---

### 2.2 Local-first, not local-only

Local-first 表示：

1. 個人資料優先保留在本機
2. 本地模型可處理低風險與高頻任務
3. 本地 vector DB / metadata DB / trace store 可獨立運作
4. 沒有雲端模型也能運行核心低風險功能
5. private raw data 與 company-sensitive data 預設不得離開本機

但本專案不是 local-only。

當任務需要高品質推理、長上下文、多文件綜合、程式碼理解、重要文件產出時，可以由 Model Router 切換到更強模型；前提是資料隱私等級允許，或已完成 redaction / summary / human approval。

---

### 2.3 Privacy-aware

所有任務進入模型前，都必須先判斷資料隱私等級。

核心 privacy levels：

```yaml
privacy_level:
  public
  private_summary
  private_raw
  company_sensitive
```

Model Router 不只看任務類型，也要看 privacy level、retrieved chunks、tool results、memory context 與最終 prompt 實際內容。

正式規則：

```text
effective_privacy_level = max(
  user_query_privacy_level,
  retrieved_chunk_privacy_level,
  tool_result_privacy_level,
  memory_context_privacy_level,
  trace_context_privacy_level
)
```

任何 generation 前都必須重新確認 `effective_privacy_level`。

---

### 2.4 Evaluation-driven

本專案不能只靠感覺判斷好壞。

需要評估：

1. RAG 是否找對資料
2. citation 是否真的支持回答
3. 模型是否知道沒有答案
4. tool calling 是否選對工具
5. tool arguments 是否有效
6. structured output 是否符合 schema
7. model routing 是否選對模型
8. privacy routing 是否遵守 policy
9. technical writing 是否可用
10. engineering analysis 是否可靠
11. latency / cost 是否可接受
12. 新版本是否 regression

LangSmith evaluation 的設計包含 dataset、evaluator、experiment 與 trace，適合做長期 eval adapter；本專案預設先做 local eval，LangSmith 作為可選 adapter，不預設上傳私人原文或真實 trace。

---

### 2.5 Trace everything

所有 Agent 執行都必須留下 trace。

Trace 需要記錄：

1. 使用者輸入
2. 任務分類
3. privacy level
4. effective privacy level
5. risk level
6. model routing decision
7. 使用模型
8. 檢索到的 chunks
9. citations
10. citation validation result
11. tool calls
12. tool arguments
13. permission gate decision
14. human approval decision
15. model response
16. structured output
17. latency
18. token usage
19. error / retry / fallback
20. eval result

本專案以 local trace store 為預設，LangSmith adapter 只用於 selected non-private runs 或 redacted traces。

---

### 2.6 Human-in-the-loop for high-risk actions

高風險工具不能由模型直接執行。

高風險工具包括：

```text
write_file
delete_file
run_shell
git_commit
git_push
send_email
network_request
calendar_write
production_operation
```

必須經過：

```text
tool request
→ permission gate
→ capability boundary check
→ human approval
→ execution
→ trace
```

LangChain HITL middleware 可以針對 tool call policy 暫停執行並等待人工決策；LangGraph interrupt 可以暫停 graph execution，保存 state，等待外部輸入後再 resume。HITL 流程必須搭配 checkpointer 與 thread_id，否則無法可靠保存與恢復狀態。

---

## 3. Scope

本專案分成 Core System、Core Apps、Advanced Apps、Out of Scope。這不是階段切分，而是定義主從關係，避免專案失焦。

---

### 3.1 Core System

Core System 是整個平台的必備能力。

1. LangGraph Runtime
2. Model Router
3. Privacy Router
4. RAG Layer
5. Tool Registry
6. Permission Gate
7. Tool Capability Boundary
8. Structured Output Layer
9. Trace Store
10. Eval Harness
11. CLI
12. Local API
13. Web Dashboard

---

### 3.2 Core Apps

Core Apps 是此專案的主要應用價值。

1. Research Memory Agent
2. Research Synthesis Agent
3. Daily Digest Agent
4. Topic Explorer Agent
5. Technical Writing Agent
6. Project Planning Agent

---

### 3.3 Advanced Apps

Advanced Apps 可以存在，但不應被描述成 local 9B 的核心能力。它們是 model-routed applications，也是 portfolio showcases，不是 Core System dependency。

1. Engineering Analysis Agent
2. Static Scan Analysis
3. Code Review Assistance
4. Architecture Review
5. Log / CI Failure Analysis

設計原則：

```text
simple explanation → local_fast
complex reasoning → cloud_reasoning
code-heavy task → code_specialist
high-risk decision → multi-model + human review
```

限制：

1. Core System 完成前，Advanced Apps 只使用 sample data
2. 不接真實公司 code
3. 不接真實 scan finding
4. 不接真實 MR diff
5. 不直接產生 git commit / push
6. 不作為安全決策唯一依據

---

### 3.4 Out of Scope

本專案不做：

1. 通用聊天機器人
2. auto-commit coding bot
3. 自動 merge / deploy
4. 直接讓 agent 修改重要檔案
5. 只用 local 9B 硬扛所有任務
6. 把私人資料公開
7. 沒有 eval 的 demo
8. 沒有 trace 的黑盒 agent
9. 全部丟給 prebuilt ReAct agent 的黑盒流程
10. 沒有 permission boundary 的 shell agent
11. 沒有 privacy enforcement 的 cloud RAG

---

## 4. System Architecture

```text
Personal R&D Agent OS
│
├── User Interfaces
│   ├── CLI
│   ├── Web UI
│   ├── Local API
│   └── Optional Editor / Notes Integration
│
├── Agent Runtime
│   ├── LangGraph Orchestrator
│   ├── Task Router
│   ├── Privacy Router
│   ├── Effective Privacy Calculator
│   ├── Model Router
│   ├── Tool Router
│   ├── Permission Gate
│   ├── Tool Capability Boundary
│   ├── State Manager
│   ├── Memory Manager
│   └── Trace / Eval Hooks
│
├── Core Applications
│   ├── Research Memory Agent
│   ├── Research Synthesis Agent
│   ├── Daily Digest Agent
│   ├── Topic Explorer Agent
│   ├── Technical Writing Agent
│   └── Project Planning Agent
│
├── Advanced Applications
│   ├── Engineering Analysis Agent
│   ├── Static Scan Analysis
│   ├── Code Review Assistance
│   ├── Architecture Review
│   └── CI / Log Analysis
│
├── Knowledge Layer
│   ├── Markdown Notes
│   ├── Work Notes
│   ├── Research Papers
│   ├── Technical Reports
│   ├── Slides / Proposals
│   ├── Code / Diff / Logs
│   └── Eval Datasets
│
├── Retrieval Layer
│   ├── Markdown Parser
│   ├── Frontmatter Parser
│   ├── Heading-aware Chunker
│   ├── Semantic Search
│   ├── Keyword Search
│   ├── Metadata Filter
│   ├── Hybrid Rank Fusion
│   ├── Reranker
│   ├── Context Packer
│   └── Citation Builder
│
├── Model Layer
│   ├── local_fast
│   │   └── qwythos-9b-q4 via llama.cpp
│   ├── cloud_reasoning
│   ├── long_context
│   ├── code_specialist
│   ├── embedding
│   ├── reranker
│   └── judge
│
└── Evaluation / Observability
    ├── RAG Eval
    ├── Citation Eval
    ├── Tool Eval
    ├── Structured Output Eval
    ├── Synthesis Eval
    ├── Engineering Eval
    ├── Model Routing Eval
    ├── Privacy Routing Eval
    ├── Latency / Cost Benchmark
    ├── Trace Viewer
    └── Feedback Loop
```

---

## 5. Technology Stack

| 層級                  | 技術                               | 用途                                                       | 理由                                                      |
| ------------------- | -------------------------------- | -------------------------------------------------------- | ------------------------------------------------------- |
| Agent Orchestration | LangGraph v1                     | StateGraph / checkpoint / HITL / persistence / streaming | 適合 stateful、多步、可中斷、可追蹤 Agent                            |
| LLM App Framework   | LangChain v1                     | model / tool / middleware / structured output            | 可接多模型與工具，適合 agent application layer                     |
| Local Runtime       | llama.cpp server                 | 本地 OpenAI-compatible LLM API                             | 已實測 Qwythos 可用                                          |
| Local Model         | Qwythos-9B Q4_K_M                | 低成本低風險任務                                                 | 適合 local_fast                                           |
| Cloud Model         | configurable                     | 深度推理、寫作、規劃、重要分析                                          | 不被小模型限制                                                 |
| Code Model          | configurable                     | 工程分析、diff、static scan                                    | 專責 code reasoning                                       |
| Embedding           | local/cloud configurable         | 向量化文件                                                    | 平衡品質、成本、隱私                                              |
| Vector DB           | LanceDB                          | 本地向量儲存                                                   | 支援 local path 連接，適合 embedded personal knowledge base 起步 |
| Keyword Search      | SQLite FTS5                      | 關鍵字查詢                                                    | 本地、簡單、可與 metadata store 整合                              |
| Metadata DB         | SQLite 起步，Postgres 可升級           | metadata / runs / eval / trace                           | 本地簡單、可長期演進                                              |
| Backend             | FastAPI                          | Web/API 服務                                               | 清楚、好整合                                                  |
| CLI                 | Typer                            | 命令列工具                                                    | 適合日常使用                                                  |
| Web UI              | Next.js or Streamlit             | dashboard / trace / eval / demo                          | 作品展示與實用介面                                               |
| Eval                | local eval + optional LangSmith  | 回歸測試與品質追蹤                                                | 可持續優化                                                   |
| Observability       | local trace + optional LangSmith | agent execution 可視化                                      | 不綁雲端                                                    |
| Scheduler           | launchd / cron                   | daily digest                                             | macOS 本地自動化                                             |
| Package             | uv / pyproject                   | Python 專案管理                                              | 現代化、乾淨                                                  |
| CI                  | GitHub Actions                   | lint / tests / sample eval                               | 履歷與工程完整度                                                |

---

## 6. LangChain v1 / LangGraph v1 Design

### 6.1 LangChain 的角色

LangChain 用於：

1. model integrations
2. tool definitions
3. middleware
4. structured output
5. local agent harness
6. retriever integration
7. output parser
8. selected simple agent loops

LangChain v1 的 `create_agent` 可處理 tools、middleware、structured output 等 agent 應用層能力；structured output 可透過 `response_format` 設定，結果回到 agent state 的 `structured_response` key。

本專案規則：

```text
create_agent 只能用於局部、低風險、可替換的 agent loop。
核心任務流程必須由 LangGraph StateGraph 顯式控制。
```

---

### 6.2 LangGraph 的角色

LangGraph 用於：

1. StateGraph workflow
2. nodes / edges / conditional routing
3. subgraphs
4. checkpoint-based persistence
5. streaming
6. human-in-the-loop
7. interrupt / resume
8. stateful workflow
9. thread-scoped execution state
10. traceable orchestration

LangGraph 是 orchestration runtime，不是單純聊天 agent。核心 workflow 應使用 StateGraph 顯式定義 nodes、edges、conditional routing，而不是把主要流程全部交給黑盒 ReAct agent。

---

### 6.3 Durable Execution 用語定義

本專案中的 durable execution 指：

```text
checkpoint-based resumable graph execution
```

也就是 LangGraph 透過 checkpointer 保存 graph state，使 interrupted run 可以 resume，使 trace、HITL、memory、fault recovery 更可靠。LangGraph checkpointer 會將 graph state 以 checkpoint 形式保存於 thread 之下；thread_id 是保存與恢復 checkpoint 的 primary key。

本專案不把 LangGraph 視為完整 job scheduler。

以下能力由外部工具負責：

1. 排程
2. 長時間 background job
3. retry watchdog
4. 批次任務
5. 定期 digest
6. 長時間 index rebuild

對應工具：

```text
launchd
cron
GitHub Actions
external job runner
```

---

### 6.4 Core Workflow Rule

本專案採用以下規則：

```text
核心 workflow：LangGraph StateGraph
局部簡單 agent：LangChain create_agent
高風險操作：LangGraph interrupt + Permission Gate
結構化輸出：獨立 formatter pass 或 LangChain structured output
```

---

### 6.5 不使用黑盒 ReAct 作為主流程

不要設計成：

```text
user input → prebuilt agent → answer
```

應設計成：

```text
user input
→ classify_task
→ assess_privacy
→ retrieve / tools
→ calculate_effective_privacy
→ model_router
→ selected subgraph
→ generation / formatter
→ quality checks
→ trace
→ eval
```

原因：

1. 可追蹤
2. 可調試
3. 可評估
4. 可替換模型
5. 可加入 permission gate
6. 可加入 privacy policy
7. 可做 regression test
8. 可避免工具與模型權限混在一起
9. 可讓 routing decision 被明確記錄

---

## 7. LangGraph Runtime Spec

### 7.1 Global State

```python
from typing import TypedDict, List, Dict, Any, Optional


class RequestState(TypedDict):
    run_id: str
    thread_id: str
    user_id: str
    user_query: str
    task_type: str
    task_intent: str


class PolicyState(TypedDict):
    risk_level: str
    user_query_privacy_level: str
    retrieved_max_privacy_level: str
    tool_result_privacy_level: str
    memory_context_privacy_level: str
    effective_privacy_level: str
    external_model_allowed: bool
    requires_user_confirmation: bool


class ModelState(TypedDict):
    model_profile: str
    fallback_model_profile: Optional[str]
    model_routing_reason: str
    model_capabilities: Dict[str, Any]


class RetrievalState(TypedDict):
    retrieved_docs: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    citation_validation_result: Optional[Dict[str, Any]]


class ToolState(TypedDict):
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    permission_decisions: List[Dict[str, Any]]
    approval_required: bool
    approved: bool


class OutputState(TypedDict):
    messages: List[Dict[str, Any]]
    draft_answer: Optional[str]
    final_answer: Optional[str]
    structured_output: Optional[Dict[str, Any]]


class RuntimeState(TypedDict):
    metrics: Dict[str, Any]
    errors: List[Dict[str, Any]]
    eval_result: Optional[Dict[str, Any]]
    trace_saved: bool


class RDState(
    RequestState,
    PolicyState,
    ModelState,
    RetrievalState,
    ToolState,
    OutputState,
    RuntimeState,
):
    pass
```

---

### 7.2 Root Graph

```text
START
  ↓
classify_task
  ↓
assess_query_privacy
  ↓
assess_risk
  ↓
select_workflow
  ├── research_memory_graph
  ├── synthesis_graph
  ├── digest_graph
  ├── topic_graph
  ├── writing_graph
  ├── planning_graph
  ├── engineering_analysis_graph
  └── eval_graph
          ↓
calculate_effective_privacy
          ↓
select_model_profile
          ↓
generate_or_execute
          ↓
format_output
          ↓
run_quality_checks
          ↓
save_trace
          ↓
run_optional_eval
          ↓
END
```

---

### 7.3 Standard Node Types

```text
classifier_node
query_privacy_router_node
risk_assessor_node
workflow_router_node
retriever_node
reranker_node
context_builder_node
effective_privacy_node
model_router_node
tool_planner_node
permission_gate_node
tool_executor_node
generation_node
formatter_node
citation_validator_node
quality_checker_node
eval_node
trace_writer_node
```

---

### 7.4 Subgraphs

```text
research_memory_graph
synthesis_graph
digest_graph
topic_graph
writing_graph
planning_graph
engineering_analysis_graph
eval_graph
```

Subgraphs must be explicit and maintainable. Each subgraph reads and writes `RDState`.

---

### 7.5 Required Runtime Guarantees

所有正式 workflow 必須保證：

1. 每個 run 有 `run_id`
2. 每個 resumable workflow 有 `thread_id`
3. 所有 node transition 可被 trace
4. 所有 model routing decision 可被保存
5. 所有 privacy decision 可被保存
6. 所有 high-risk tool call 必須 interrupt
7. 所有 structured output 必須 schema validation
8. 所有 citation 必須能映射回 indexed chunk
9. 所有 error / retry / fallback 必須可追蹤
10. 所有 eval report 必須能關聯到 code version / config version / model version

---

## 8. Model Router

### 8.1 Purpose

Model Router 是本專案不被模型限制的核心。

負責：

1. 根據 task_type 選模型
2. 根據 effective_privacy_level 選模型
3. 根據 risk_level 選模型
4. 根據 context_size 選模型
5. 根據 quality_requirement 選模型
6. 根據 cost_budget 選模型
7. 根據 latency requirement 選模型
8. 根據 tool requirement 選模型
9. 根據 output value level 選模型
10. 根據 eval 結果調整 policy
11. 在失敗時 fallback
12. 記錄 routing decision

---

### 8.2 Model Profiles

```yaml
models:
  local_fast:
    provider: openai_compatible
    base_url: http://10.10.10.12:8080/v1
    model: qwythos-9b-q4
    strengths:
      - low_cost
      - local
      - private
      - simple_summary
      - metadata_extraction
      - low_risk_rag
      - formatting
      - daily_digest_draft
    avoid:
      - deep_code_review
      - cross_file_reasoning
      - security_decision
      - long_horizon_planning
      - high_value_writing
      - long_context_synthesis

  cloud_reasoning:
    provider: configurable
    model: configurable
    strengths:
      - deep_reasoning
      - research_synthesis
      - proposal_writing
      - project_planning
      - technical_report_generation
      - decision_memo

  long_context:
    provider: configurable
    model: configurable
    strengths:
      - long_document_analysis
      - multi_note_synthesis
      - paper_review
      - report_review
      - large_context_planning

  code_specialist:
    provider: configurable
    model: configurable
    strengths:
      - code_review
      - diff_analysis
      - static_scan_analysis
      - architecture_review
      - log_analysis
      - ci_failure_analysis

  embedding:
    provider: local_or_cloud
    model: configurable

  reranker:
    provider: local_or_cloud
    model: configurable

  judge:
    provider: configurable
    model: configurable
    strengths:
      - answer_evaluation
      - faithfulness_check
      - writing_quality_check
      - routing_eval
      - citation_eval
```

---

### 8.3 Routing Decision Schema

```json
{
  "selected_model_profile": "local_fast",
  "fallback_model_profile": "cloud_reasoning",
  "reason": "effective privacy level is private_raw, so external models are blocked",
  "task_type": "research_memory",
  "risk_level": "low",
  "user_query_privacy_level": "private_raw",
  "retrieved_max_privacy_level": "private_raw",
  "tool_result_privacy_level": "none",
  "memory_context_privacy_level": "private_raw",
  "effective_privacy_level": "private_raw",
  "external_model_allowed": false,
  "requires_user_confirmation": false,
  "expected_cost_level": "low",
  "expected_latency_level": "low"
}
```

---

### 8.4 Important LangChain v1 Rule

Model Router 不應回傳已經 `bind_tools()` 的 pre-bound model。

錯誤設計：

```python
model = ChatOpenAI(...).bind_tools(tools)
return model
```

正確設計：

```text
Model Router 只回傳：
1. model_profile
2. provider
3. model_name
4. capability flags
5. routing reason
```

Tool binding / structured output strategy 由 workflow node 決定。

原因是 dynamic model selection、tool binding、structured output 在 LangChain v1 裡需要小心分層，避免模型已預先綁定工具後無法根據 runtime state 正確切換工具或 schema。

---

### 8.5 Suggested Routing Rules

| 任務                  | 預設模型                              | 原因                           |
| ------------------- | --------------------------------- | ---------------------------- |
| 短摘要                 | local_fast                        | 低成本、本地足夠                     |
| metadata extraction | local_fast                        | 結構簡單                         |
| tag 建議              | local_fast                        | 可重試                          |
| daily digest draft  | local_fast                        | 可本地產生草稿                      |
| daily digest final  | cloud_reasoning if allowed        | 最終稿需要更好整合                    |
| RAG 問答              | local_fast 起步，必要時 cloud_reasoning | 依問題難度與 privacy 切換            |
| 多篇研究綜合              | cloud_reasoning / long_context    | 需要深度整合                       |
| 技術提案                | cloud_reasoning                   | 需要結構與說服力                     |
| 履歷文件                | cloud_reasoning                   | 高價值輸出                        |
| Code Review         | code_specialist                   | 小模型不應主審                      |
| Static Scan 分析      | code_specialist                   | 需要 code / security reasoning |
| eval judge          | judge                             | 需要一致性                        |
| JSON formatter      | local_fast                        | 可控、低成本                       |

---

### 8.6 Fallback Rules

```text
local_fast failed schema validation twice
→ fallback to cloud_reasoning if privacy allows
→ otherwise return structured error

cloud_reasoning timeout
→ fallback to long_context if compatible
→ otherwise return partial answer with trace

code_specialist unavailable
→ fallback to cloud_reasoning only for public/sample code
→ company_sensitive code cannot fallback to external model
```

---

## 9. Privacy Routing Policy

### 9.1 Privacy Levels

```yaml
privacy_levels:
  public:
    description: 可送雲端模型
    examples:
      - 公開論文
      - 官方文件
      - 公開文章
      - sample data

  private_summary:
    description: 去識別化摘要，可在使用者確認後送雲端
    examples:
      - 人工整理後的摘要
      - 移除公司名稱與機密細節的技術問題
      - redacted project notes

  private_raw:
    description: 原文不可送雲端，預設只能 local
    examples:
      - 完整個人筆記
      - 私人工作紀錄
      - 本機 trace
      - 未清洗的會議記錄

  company_sensitive:
    description: 公司敏感資料，不可送外部模型
    examples:
      - 公司 code
      - 真實 MR diff
      - 內部 scan finding
      - 公司架構文件
      - 私有 log
```

---

### 9.2 Privacy Routing Rules

```yaml
public:
  allowed_profiles:
    - local_fast
    - cloud_reasoning
    - long_context
    - code_specialist

private_summary:
  allowed_profiles:
    - local_fast
    - cloud_reasoning
    - long_context
  requires_confirmation_for_cloud: true

private_raw:
  allowed_profiles:
    - local_fast
  requires_redaction_for_cloud: true

company_sensitive:
  allowed_profiles:
    - local_fast
  external_model_allowed: false
```

---

### 9.3 Effective Privacy Level

Model Router 不得只依照 user query 判斷 privacy level。

實際送入模型的 prompt 可能包含：

1. user query
2. retrieved chunks
3. tool results
4. memory context
5. previous state
6. trace summary

因此每次 generation 前都必須計算 `effective_privacy_level`。

```text
effective_privacy_level = max(
  user_query_privacy_level,
  retrieved_chunk_privacy_level,
  tool_result_privacy_level,
  memory_context_privacy_level,
  trace_context_privacy_level
)
```

Privacy level 風險排序：

```text
public < private_summary < private_raw < company_sensitive
```

---

### 9.4 Privacy Checkpoints

Privacy routing 必須至少執行三次：

```text
before_retrieval:
  classify user query privacy
  decide allowed retrieval scope

after_retrieval:
  aggregate retrieved chunk privacy levels
  calculate effective_privacy_level

before_generation:
  verify final prompt privacy boundary
  block external model if policy does not allow it
```

---

### 9.5 Hard Privacy Rule

`company_sensitive` 與 `private_raw` content 不得進入 external model prompt。

唯一例外：

1. 先經過 redaction pipeline
2. 產生 `private_summary` artifact
3. 使用者明確允許 cloud escalation
4. trace 記錄 approval decision
5. final prompt 經過 privacy validator 通過

---

### 9.6 Trace Privacy Rule

Trace 預設保留在 local。

不可預設送出的內容：

1. private raw notes
2. company-sensitive data
3. real traces
4. raw tool arguments
5. full retrieved chunks
6. raw user query containing private content

若要匯出 LangSmith 或其他 cloud observability：

```text
trace → redaction → privacy validation → user approval → export
```

---

### 9.7 Privacy Routing Decision Schema

```json
{
  "user_query_privacy_level": "private_raw",
  "retrieved_max_privacy_level": "private_raw",
  "tool_result_privacy_level": "none",
  "memory_context_privacy_level": "private_raw",
  "effective_privacy_level": "private_raw",
  "external_model_allowed": false,
  "selected_model_profile": "local_fast",
  "reason": "raw private data cannot be sent to external models",
  "requires_redaction_for_cloud": true,
  "requires_user_confirmation": false
}
```

---

## 10. RAG System

### 10.1 RAG Design Principle

本系統的 RAG 不是單純：

```text
query → vector search top-k → answer
```

而是：

```text
query understanding
→ query rewrite
→ semantic search
→ keyword search
→ metadata filter
→ hybrid rank fusion
→ rerank
→ chunk read
→ context packing
→ citation map
→ answer generation
→ citation validation
```

---

### 10.2 Document Schema

所有 schema key 使用英文。

```json
{
  "doc_id": "20260624-enterprise-rag-filtering",
  "source_type": "markdown_note",
  "file_path": "/Users/oliver/Workspace/notes/AI/...",
  "title": "企業 RAG 的檢索本質",
  "date": "2026-06-24",
  "tags": ["RAG", "enterprise", "retrieval"],
  "folder": "AI/RAG",
  "heading_path": "4.1 Anchor",
  "chunk_id": "20260624-enterprise-rag-filtering::12",
  "chunk_text": "...",
  "token_count": 420,
  "content_hash": "sha256:...",
  "chunk_hash": "sha256:...",
  "privacy_level": "private_raw",
  "created_at": "2026-06-24T10:00:00+08:00",
  "updated_at": "2026-07-04T20:00:00+08:00"
}
```

---

### 10.3 Chunking Strategy

因為資料以 Markdown 為主，採用 heading-aware chunking。

1. 解析 YAML frontmatter
2. 保留 title / date / tags / summary
3. 依 heading 切分
4. 保留 heading_path
5. chunk 目標 300–600 tokens
6. 太長的 heading section 再切小
7. overlap 80–120 tokens
8. 每個 chunk 保留 source metadata
9. 每個 chunk 計算 `chunk_hash`
10. 每份文件計算 `content_hash`
11. 每個 chunk 必須有 privacy_level
12. 文件更新後，舊 chunk citation 標記為 stale

---

### 10.4 Retrieval Modes

#### fast_rag

用於簡單問答。

```text
query → rewrite → top-k retrieval → rerank → answer
```

#### agentic_rag

用於需要多次查詢與逐段閱讀的問題。

```text
query → search_notes → read_note → search_related → answer
```

#### synthesis_rag

用於多篇整理。

```text
topic → retrieve many notes → cluster → summarize clusters → synthesize
```

#### evidence_rag

用於需要 citation 嚴格支持的輸出。

```text
claim → retrieve evidence → validate support → cite → answer
```

---

### 10.5 Hybrid Retrieval

Hybrid retrieval 使用：

```text
Semantic Search: LanceDB
Keyword Search: SQLite FTS5
Metadata Filter: SQLite metadata store
Rank Fusion: reciprocal rank fusion or weighted score
Reranker: local or cloud configurable
```

Private raw / company-sensitive data 預設使用 local embedding 與 local reranker。

---

### 10.6 Citation Requirements

每個重要結論都必須能追溯到具體 chunk，且 citation 必須可被 eval 驗證。

Citation schema：

```json
{
  "doc_id": "20260624-enterprise-rag-filtering",
  "file_path": "notes/AI/RAG/260624-enterprise-rag-filtering.md",
  "title": "企業 RAG 的檢索本質",
  "heading_path": "4.1 Anchor",
  "chunk_id": "20260624-enterprise-rag-filtering::12",
  "chunk_hash": "sha256:...",
  "content_hash": "sha256:...",
  "start_char": 10240,
  "end_char": 10880,
  "retrieval_score": 0.82,
  "rerank_score": 0.91,
  "evidence_quote": "short quote only",
  "evidence_summary": "該段落說明 anchor 如何穩定 retrieval entry point"
}
```

Citation validation 至少檢查：

1. citation 是否對應存在的 chunk
2. chunk_hash 是否符合目前 indexed version
3. answer claim 是否被 cited chunk 支持
4. citation 不可引用未進入 context 的資料
5. 文件更新後，舊 citation 必須標記為 stale

---

### 10.7 Context Packing Rules

Context packing 需考慮：

1. task_type
2. model context limit
3. privacy level
4. retrieval score
5. rerank score
6. heading diversity
7. source diversity
8. citation coverage
9. duplicate chunks
10. stale chunk exclusion

Context packer 不得把 privacy policy 禁止的資料放進 external model prompt。

---

## 11. Agent Applications

### 11.1 Research Memory Agent

#### Purpose

查詢自己過去讀過、整理過、思考過的資料。

#### Example Queries

```text
我之前是不是看過 X？
我整理過哪些關於 Y 的資料？
哪幾篇筆記提到 Z？
這篇文章跟我之前哪篇筆記有關？
我對某個技術的歷史判斷是什麼？
```

#### Workflow

```text
user question
  ↓
query classification
  ↓
query rewrite
  ↓
hybrid retrieval
  ↓
rerank
  ↓
context packing
  ↓
effective privacy calculation
  ↓
model routing
  ↓
answer generation
  ↓
citation validation
  ↓
structured output
  ↓
trace
```

#### Output Schema

```json
{
  "answer_status": "answered",
  "answer": "string",
  "citations": [
    {
      "doc_id": "string",
      "file_path": "string",
      "heading_path": "string",
      "chunk_id": "string",
      "evidence_summary": "string"
    }
  ],
  "related_notes": [
    {
      "file": "string",
      "reason": "string"
    }
  ],
  "confidence": "high",
  "missing_context": []
}
```

---

### 11.2 Research Synthesis Agent

#### Purpose

把多篇筆記整理成有結構的研究報告。

#### Example Tasks

```text
整理我所有關於 Agent Evaluation 的筆記
比較 LangGraph / AutoGen / CrewAI / LlamaIndex
把 local LLM serving 的筆記整理成技術報告
整理 RAG evaluation 的方法與指標
從我的筆記中整理出一份主管簡報大綱
```

#### Workflow

```text
topic input
  ↓
topic expansion
  ↓
retrieve candidate notes
  ↓
aggregate effective privacy
  ↓
cluster notes
  ↓
select representative evidence
  ↓
generate outline
  ↓
generate synthesis
  ↓
citation check
  ↓
quality check
  ↓
save report
```

---

### 11.3 Daily Digest Agent

#### Purpose

每天自動整理新增或修改的研究資料。

#### Workflow

```text
find changed notes
  ↓
load note metadata
  ↓
summarize each note
  ↓
detect common topics
  ↓
retrieve related old notes
  ↓
generate digest
  ↓
save markdown
  ↓
update index
```

#### Output Template

```md
# Daily R&D Digest - YYYY-MM-DD

## 今日新增主題

## 今日重點

## 與既有筆記關聯

## 值得重讀

## 可延伸成工作提案的方向

## 可寫成文章的題目
```

---

### 11.4 Topic Explorer Agent

#### Purpose

分析長期研究主題的分布、趨勢與盲點。

#### Example Queries

```text
最近 30 天我最常研究什麼？
Agent Evaluation 這個主題有哪些分支？
我關於 local LLM 的筆記主要集中在哪些方向？
哪些主題讀很多但還沒寫成文章？
哪些主題可以轉成工作提案？
```

#### Output

1. 主題地圖
2. 時間線
3. 熱度排名
4. 代表筆記
5. 關聯主題
6. 盲點
7. 建議輸出方向

---

### 11.5 Technical Writing Agent

#### Purpose

把研究筆記與想法轉成可用文件。

#### Supported Output Types

```text
technical_report
proposal
weekly_report
executive_summary
slides_outline
linkedin_post
patent_idea_note
architecture_doc
decision_record
```

#### Workflow

```text
writing request
  ↓
identify target audience
  ↓
retrieve supporting notes
  ↓
calculate effective privacy
  ↓
select model profile
  ↓
generate outline
  ↓
draft document
  ↓
check citation / evidence
  ↓
style refinement
  ↓
final output
```

---

### 11.6 Project Planning Agent

#### Purpose

把想法變成可執行計畫。

#### Supported Tasks

```text
side project planning
PoC planning
tool evaluation planning
architecture planning
roadmap planning
risk analysis
decision memo
```

#### Output

1. 目標
2. 背景
3. 範圍
4. 非目標
5. 架構
6. 資料流
7. 風險
8. 驗證方式
9. 成果定義
10. 履歷價值

---

### 11.7 Engineering Analysis Agent

#### Positioning

Engineering Analysis 是 Advanced App，不是 local 9B core capability。

它用來展示 RDOS runtime 的可擴充性，但不阻塞 Core System。

#### Supported Tasks

```text
code review assistance
static scan explanation
architecture review
log analysis
CI/CD failure analysis
security finding explanation
```

#### Model Policy

```text
simple explanation → local_fast
complex code reasoning → code_specialist
architecture review → cloud_reasoning
high-risk security decision → multi-model + human review
```

#### Output Schema

```json
{
  "task_type": "engineering_analysis",
  "summary": "string",
  "findings": [
    {
      "category": "string",
      "severity": "medium",
      "evidence": "string",
      "recommendation": "string"
    }
  ],
  "confidence": "medium",
  "requires_human_review": true,
  "model_profile_used": "code_specialist"
}
```

---

## 12. Tool System and Permission Gate

### 12.1 Tool Categories

#### Knowledge Tools

```text
search_notes
read_note
list_recent_notes
find_related_notes
get_topic_timeline
```

#### Document Tools

```text
parse_markdown
parse_pdf
summarize_document
extract_metadata
```

#### Writing Tools

```text
create_outline
rewrite_section
generate_report
generate_slide_outline
```

#### Engineering Tools

```text
read_diff
parse_scan_finding
search_code_context
explain_stack_trace
classify_issue
```

#### Eval Tools

```text
run_rag_eval
run_tool_eval
run_schema_eval
compare_model_outputs
run_privacy_eval
run_model_routing_eval
```

#### System Tools

```text
save_trace
save_digest
update_index
export_report
```

---

### 12.2 Permission Levels

```yaml
low:
  - read_note
  - search_notes
  - list_recent_notes
  - summarize_document
  - calculator

medium:
  - read_local_file
  - parse_diff
  - read_project_context
  - export_report

high:
  - write_file
  - run_shell
  - delete_file
  - git_commit
  - git_push
  - send_email
  - network_request
```

---

### 12.3 Permission Decision Schema

```json
{
  "tool_name": "read_note",
  "risk_level": "low",
  "allowed": true,
  "requires_approval": false,
  "reason": "read_note is limited to configured notes directory"
}
```

---

### 12.4 Tool Capability Boundary

Permission Gate 不只判斷 tool name，也必須判斷 tool scope、argument、side effect 與 execution boundary。

每個 tool 必須定義：

```json
{
  "tool_name": "read_local_file",
  "permission_level": "medium",
  "allowed_roots": [
    "~/Workspace/personal-rd-agent-os/sample_data",
    "~/Workspace/notes"
  ],
  "blocked_patterns": [
    ".env",
    "id_rsa",
    "credentials",
    "secrets",
    "company"
  ],
  "max_bytes": 200000,
  "requires_approval": true
}
```

`run_shell` 必須使用 allowlist，不可讓模型自由執行任意 shell command。

```json
{
  "tool_name": "run_shell",
  "permission_level": "high",
  "allowed_commands": [
    "pytest",
    "ruff",
    "mypy",
    "git diff",
    "git status"
  ],
  "blocked_commands": [
    "rm",
    "curl",
    "scp",
    "ssh",
    "git push",
    "chmod",
    "sudo"
  ],
  "requires_approval": true,
  "requires_human_review": true
}
```

High-risk tool execution 必須記錄：

1. original tool call
2. normalized arguments
3. permission decision
4. human approval result
5. execution result
6. idempotency key
7. trace id

---

### 12.5 Implementation Strategy

Permission Gate 有兩種實作方式。

#### Simple Agent Flow

使用 LangChain human-in-the-loop middleware。

適合簡單 `create_agent` tool call flow。LangChain HITL middleware 可根據 tool call policy 暫停執行並等待人工決策。

#### Custom Graph Flow

使用 LangGraph interrupt + persistence。

適合本專案核心 StateGraph workflow。LangGraph interrupts 可以暫停 graph execution，保存 state，等待外部輸入後再 resume。

---

### 12.6 HITL Runtime Requirements

所有 high-risk tool approval 都必須支援 resumable execution。

要求：

1. LangGraph workflow 必須啟用 checkpointer
2. 每次 run 必須有 thread_id
3. approval decision 必須寫入 trace
4. resume 時必須檢查原始 tool arguments 是否被竄改
5. high-risk tool 必須有 idempotency key
6. 已執行過的 high-risk action 不可因 replay 被重複執行
7. production mode 不可使用 purely in-memory approval state
8. approval UI 必須展示 tool name、argument、risk、side effect
9. denied action 必須保存 reason
10. approved action 必須保存 approver identity 或 local user marker

---

## 13. Structured Output

### 13.1 LangChain v1 Structured Output

LangChain v1 的 `create_agent` 支援透過 `response_format` 產生 structured output。當模型產生結構化資料時，結果會被驗證並回到 agent state 的 `structured_response` key。

但本專案需要注意：

```text
本地 llama.cpp 是 OpenAI-compatible，不等於完整 OpenAI provider-native structured output。
```

llama.cpp server 文件顯示 `response_format` 支援 plain JSON output 與 schema-constrained JSON；但 OpenAI-compatible runtime 與 LangChain structured output 的實際相容性仍必須以 adapter compatibility tests 驗證。

---

### 13.2 Strategy

本專案採用以下策略：

1. Provider-native structured output
   只在 provider 明確可靠時使用

2. ToolStrategy
   用於支援 tool calling 但 provider-native structured output 不穩的模型

3. Independent formatter pass
   用於本地 llama.cpp、Qwythos、或任何需要嚴格控制 schema 的場景

LangChain agents 文件說明，ToolStrategy 適合 provider-native structured output 不可用或不可靠時使用。

---

### 13.3 Qwythos / llama.cpp 實測規則

根據本地實測，本專案採用：

1. JSON schema key 永遠使用英文
2. description 可以繁中
3. enum value 可以繁中或英文，但核心 enum 建議用英文
4. JSON formatter 任務關閉 thinking
5. tool planning 與 final structured formatter 分離
6. high-value output 使用 Pydantic validation
7. validation failed 時重試一次
8. 第二次失敗則 fallback stronger model
9. privacy 不允許 fallback 時，回傳 structured error
10. schema validation error 必須進 trace

---

### 13.4 Two-pass Output Rule

正式規則：

```text
tool planning pass:
  tools enabled
  no strict final schema

execution pass:
  app executes tools

final answer pass:
  normal generation or streaming

formatter pass:
  structured output
  thinking off
  schema enabled
```

這可以降低 tool calling、streaming、structured output 互相干擾的風險。

---

### 13.5 Research Answer Schema

```json
{
  "answer_status": "answered",
  "answer": "string",
  "citations": [
    {
      "doc_id": "string",
      "file_path": "string",
      "heading_path": "string",
      "chunk_id": "string",
      "evidence_summary": "string"
    }
  ],
  "confidence": "high",
  "missing_context": []
}
```

---

### 13.6 Digest Schema

```json
{
  "date": "2026-07-04",
  "new_topics": ["string"],
  "key_points": ["string"],
  "related_notes": [
    {
      "file": "string",
      "reason": "string"
    }
  ],
  "suggested_outputs": [
    {
      "type": "proposal",
      "title": "string",
      "reason": "string"
    }
  ]
}
```

---

### 13.7 Engineering Analysis Schema

```json
{
  "task_type": "engineering_analysis",
  "summary": "string",
  "findings": [
    {
      "category": "string",
      "severity": "medium",
      "evidence": "string",
      "recommendation": "string"
    }
  ],
  "confidence": "medium",
  "requires_human_review": true,
  "model_profile_used": "code_specialist"
}
```

---

## 14. Trace and Observability

### 14.1 Local-first Trace

Default:

```text
local trace store
local SQLite / JSONL
local eval report
```

Optional:

```text
LangSmith adapter for selected non-private runs
```

不可預設送出：

1. private raw notes
2. company-sensitive data
3. real traces
4. raw retrieved chunks
5. raw tool arguments

---

### 14.2 Trace Schema

```json
{
  "run_id": "uuid",
  "thread_id": "thread-uuid",
  "timestamp": "2026-07-04T20:00:00+08:00",
  "task_type": "research_memory",
  "privacy": {
    "user_query_privacy_level": "private_raw",
    "retrieved_max_privacy_level": "private_raw",
    "effective_privacy_level": "private_raw",
    "external_model_allowed": false
  },
  "risk_level": "low",
  "user_query": "我之前是不是看過一篇講 RAG filtering 的文章？",
  "model_profile": "local_fast",
  "model_routing_reason": "private raw notes must stay local",
  "retrieved_docs": [
    {
      "file": "260624 企業 RAG 的檢索本質.md",
      "heading": "4.1 Anchor",
      "score": 0.87,
      "chunk_hash": "sha256:..."
    }
  ],
  "citations": [
    {
      "chunk_id": "20260624-enterprise-rag-filtering::12",
      "validated": true
    }
  ],
  "tool_calls": [],
  "permission_decisions": [],
  "final_answer": "...",
  "structured_output": {},
  "metrics": {
    "latency_ms": 5120,
    "input_tokens": 4200,
    "output_tokens": 680
  },
  "errors": []
}
```

---

### 14.3 Trace Viewer

Web UI 應支援查看：

1. 每次任務的輸入
2. privacy level
3. effective privacy level
4. risk level
5. model routing decision
6. 使用的模型
7. 檢索到哪些資料
8. citation validation
9. 工具呼叫紀錄
10. 權限判斷
11. human approval decision
12. 模型輸出
13. final answer
14. token / latency
15. eval result
16. fallback reason

---

## 15. Evaluation System

### 15.1 RAG Eval

Dataset example：

```json
{
  "id": "rag-001",
  "question": "這篇筆記中 anchor 是什麼？",
  "expected_files": ["260624 企業 RAG 的檢索本質.md"],
  "expected_headings": ["4.1 Anchor"],
  "answer_type": "factual"
}
```

Metrics：

1. Recall@3
2. Recall@5
3. Citation accuracy
4. No-answer accuracy
5. Answer faithfulness
6. Latency p50 / p95

---

### 15.2 Citation Eval

Metrics：

1. citation exists rate
2. valid chunk reference rate
3. stale citation rate
4. claim support accuracy
5. citation coverage
6. unsupported claim rate

---

### 15.3 Tool Eval

Metrics：

1. tool selection accuracy
2. argument JSON validity
3. tool success rate
4. retry success rate
5. permission gate correctness
6. blocked action correctness

---

### 15.4 Structured Output Eval

Metrics：

1. JSON validity
2. schema compliance
3. enum validity
4. missing field rate
5. fallback rate
6. validation retry success rate

---

### 15.5 Synthesis Eval

Metrics：

1. source coverage
2. citation coverage
3. contradiction handling
4. topic completeness
5. usefulness
6. executive readability

---

### 15.6 Engineering Eval

Metrics：

1. root cause accuracy
2. severity accuracy
3. fix usefulness
4. human review necessity
5. evidence quality

---

### 15.7 Model Routing Eval

Metrics：

1. correct model selection
2. privacy policy compliance
3. local model usage rate
4. cloud model usage rate
5. fallback rate
6. cost
7. latency
8. quality delta

---

### 15.8 Privacy Routing Eval

Metrics：

1. privacy policy compliance
2. external model block accuracy
3. redaction requirement detection
4. effective privacy calculation accuracy
5. private_raw leakage rate
6. company_sensitive leakage rate

---

### 15.9 Eval Report Template

```md
# Personal R&D Agent OS Eval Report

## RAG

| Metric | Result |
|---|---:|
| Recall@3 | |
| Recall@5 | |
| Citation Accuracy | |
| No-answer Accuracy | |

## Citation

| Metric | Result |
|---|---:|
| Valid Chunk Reference Rate | |
| Stale Citation Rate | |
| Unsupported Claim Rate | |

## Tool Calling

| Metric | Result |
|---|---:|
| Tool Selection Accuracy | |
| Argument JSON Validity | |
| Tool Success Rate | |
| Permission Gate Correctness | |

## Structured Output

| Metric | Result |
|---|---:|
| JSON Validity | |
| Schema Compliance | |
| Fallback Rate | |

## Model Routing

| Metric | Result |
|---|---:|
| Correct Routing Rate | |
| Local Model Usage | |
| Cloud Model Usage | |
| Fallback Rate | |

## Privacy

| Metric | Result |
|---|---:|
| Privacy Policy Compliance | |
| External Model Block Accuracy | |
| Private Raw Leakage Rate | |
| Company-sensitive Leakage Rate | |
```

---

### 15.10 Release Gate

每次重要版本更新都必須執行 eval gate。

v1 release gate：

| Area              |                         Metric | Required |
| ----------------- | -----------------------------: | -------: |
| RAG               |                       Recall@5 |  >= 0.75 |
| RAG               |              Citation Accuracy |  >= 0.70 |
| RAG               |             No-answer Accuracy |  >= 0.80 |
| Citation          |     Valid Chunk Reference Rate |  >= 0.95 |
| Structured Output |                  JSON Validity |  >= 0.95 |
| Structured Output |              Schema Compliance |  >= 0.90 |
| Model Routing     |           Correct Routing Rate |  >= 0.85 |
| Privacy           |      Privacy Policy Compliance |     1.00 |
| Privacy           |       Private Raw Leakage Rate |        0 |
| Privacy           | Company-sensitive Leakage Rate |        0 |
| Tool Permission   |           Permission Violation |        0 |
| Trace             |        Trace Save Success Rate |  >= 0.99 |

如果 release gate 未通過，不得標記為 stable version。

---

## 16. llama.cpp + LangChain Compatibility Tests

你已經用 curl 驗證 llama.cpp / Qwythos API，但接 LangChain 之後，必須再做 adapter compatibility test。

llama.cpp / llama-cpp-python 提供 OpenAI-compatible server，可接現有 OpenAI-compatible clients；但 function calling、structured output、response_format、extra_body、reasoning fields、tool call parsing 等行為仍要實測。

---

### 16.1 Required Tests

1. ChatOpenAI basic invoke
2. Streaming
3. Tool calling / bind_tools
4. parse_tool_calls passthrough
5. reasoning_format passthrough
6. reasoning_content 是否保留
7. chat_template_kwargs.enable_thinking 是否生效
8. response_format.json_schema 是否生效
9. structured output 是否真的 enforce schema
10. ToolStrategy 是否比 ProviderStrategy 穩定
11. independent formatter pass 是否最穩
12. token counting endpoint 是否另行封裝
13. timeout / retry / fallback 是否正確
14. malformed JSON repair 是否可控

---

### 16.2 Compatibility Result Format

```json
{
  "test_name": "structured_output_json_schema",
  "langchain_version": "x.y.z",
  "langgraph_version": "x.y.z",
  "llama_cpp_build": "commit_hash",
  "model": "qwythos-9b-q4",
  "result": "pass",
  "notes": "OpenAI nested json_schema format works only through extra_body direct call"
}
```

---

### 16.3 Fallback Rule

如果 LangChain structured output 對本地 llama.cpp 不穩：

```text
Use independent formatter pass.
Call OpenAI-compatible API directly.
Disable thinking.
Use OpenAI nested json_schema format.
Validate with Pydantic.
Retry once.
Fallback stronger model if still invalid and privacy allows.
Return structured error if privacy blocks fallback.
```

---

## 17. CLI Design

### 17.1 Index

```bash
rdos index ./sample_data/notes
rdos index ~/Workspace/notes --privacy private_raw
```

---

### 17.2 Research QA

```bash
rdos ask "我之前是不是看過一篇講 RAG 是 filtering 的文章？"
```

---

### 17.3 Research Synthesis

```bash
rdos synthesize "整理我所有 agent evaluation 筆記"
```

---

### 17.4 Daily Digest

```bash
rdos digest --today
```

---

### 17.5 Topic Explorer

```bash
rdos topic "local LLM serving" --since 2026-01-01
```

---

### 17.6 Writing

```bash
rdos write --type proposal "把本地 Agent Gateway 的設計整理成主管可看的提案"
```

---

### 17.7 Planning

```bash
rdos plan "把 Personal R&D Agent OS 做成可放履歷的 side project"
```

---

### 17.8 Engineering Analysis

```bash
rdos analyze-code --diff example.diff --model-profile code_specialist
```

---

### 17.9 Eval

```bash
rdos eval rag
rdos eval citation
rdos eval tools
rdos eval structured-output
rdos eval model-routing
rdos eval privacy
rdos eval all
```

---

### 17.10 Trace

```bash
rdos trace list
rdos trace show <run_id>
```

---

### 17.11 Policy Check

```bash
rdos policy check --input sample_query.json
rdos policy test privacy
rdos policy test tools
```

---

## 18. Web UI Design

### 18.1 Dashboard

顯示：

1. Indexed documents
2. Total chunks
3. Last indexed time
4. Today new notes
5. RAG Recall@5
6. Citation accuracy
7. Tool success rate
8. Structured output validity
9. Privacy policy compliance
10. Local model usage
11. Cloud model usage
12. Average latency

---

### 18.2 Research Memory

功能：

1. 問答
2. 顯示引用
3. 顯示 related notes
4. 顯示 confidence
5. 可打開來源筆記
6. 顯示 effective privacy level
7. 顯示 model routing decision

---

### 18.3 Topic Explorer

功能：

1. 主題搜尋
2. 時間線
3. 主題關聯圖
4. 代表筆記
5. 可輸出報告

---

### 18.4 Daily Digest

功能：

1. 今日 digest
2. 歷史 digest
3. 主題趨勢
4. 一鍵輸出 markdown

---

### 18.5 Writing Studio

功能：

1. 選擇輸出類型
2. 選擇引用資料
3. 生成草稿
4. 改寫
5. 輸出 markdown
6. citation check
7. privacy check before cloud generation

---

### 18.6 Eval Dashboard

功能：

1. RAG eval
2. Citation eval
3. Tool eval
4. Structured output eval
5. Model routing eval
6. Privacy policy compliance
7. Regression trend
8. Release gate status

---

### 18.7 Trace Viewer

功能：

1. 查看 run
2. 查看 graph steps
3. 查看 tool calls
4. 查看 permission decisions
5. 查看 model routing
6. 查看 privacy decision
7. 查看 retrieved docs
8. 查看 citation validation
9. 查看 latency / token
10. 查看 fallback reason

---

### 18.8 Web UI Scope Control

Web UI 不是本專案價值的唯一展示方式。

v1 Web UI 必須支援：

1. Research Memory Ask
2. Trace Viewer
3. Eval Dashboard

其他功能可逐步擴充：

1. Writing Studio
2. Topic Graph
3. Full Daily Digest UI
4. Report Editor
5. Advanced Engineering Analysis UI

主要展示方式仍以 CLI、Markdown output、trace JSON、eval report 為主。

---

## 19. Repository Structure

```text
personal-rd-agent-os/
├── README.md
├── pyproject.toml
├── .env.example
├── configs/
│   ├── models.yaml
│   ├── privacy_policy.yaml
│   ├── tool_policy.yaml
│   └── rag.yaml
│
├── docs/
│   ├── architecture.md
│   ├── model-routing.md
│   ├── privacy-routing.md
│   ├── privacy-enforcement.md
│   ├── langgraph-runtime.md
│   ├── rag-system.md
│   ├── citation-validation.md
│   ├── permission-gate.md
│   ├── tool-capability-boundary.md
│   ├── structured-output.md
│   ├── evaluation-methodology.md
│   ├── evaluation-release-gates.md
│   ├── observability.md
│   ├── llama-cpp-langchain-compatibility.md
│   └── resume-case-study.md
│
├── src/
│   └── rdos/
│       ├── config.py
│       ├── main.py
│       │
│       ├── llm/
│       │   ├── model_profiles.py
│       │   ├── model_router.py
│       │   ├── privacy_router.py
│       │   ├── local_llama_cpp.py
│       │   ├── cloud_models.py
│       │   └── structured_output.py
│       │
│       ├── graph/
│       │   ├── state.py
│       │   ├── root_graph.py
│       │   ├── research_memory_graph.py
│       │   ├── synthesis_graph.py
│       │   ├── digest_graph.py
│       │   ├── topic_graph.py
│       │   ├── writing_graph.py
│       │   ├── planning_graph.py
│       │   ├── engineering_graph.py
│       │   └── eval_graph.py
│       │
│       ├── rag/
│       │   ├── loaders.py
│       │   ├── markdown_parser.py
│       │   ├── chunker.py
│       │   ├── indexer.py
│       │   ├── retriever.py
│       │   ├── hybrid_search.py
│       │   ├── reranker.py
│       │   ├── query_rewriter.py
│       │   ├── context_packer.py
│       │   └── citation_builder.py
│       │
│       ├── tools/
│       │   ├── registry.py
│       │   ├── permission_gate.py
│       │   ├── capability_boundary.py
│       │   ├── knowledge_tools.py
│       │   ├── document_tools.py
│       │   ├── writing_tools.py
│       │   ├── engineering_tools.py
│       │   └── eval_tools.py
│       │
│       ├── memory/
│       │   ├── session_memory.py
│       │   ├── project_memory.py
│       │   └── preference_memory.py
│       │
│       ├── schemas/
│       │   ├── research.py
│       │   ├── synthesis.py
│       │   ├── digest.py
│       │   ├── writing.py
│       │   ├── engineering.py
│       │   ├── eval.py
│       │   ├── privacy.py
│       │   └── trace.py
│       │
│       ├── eval/
│       │   ├── rag_eval.py
│       │   ├── citation_eval.py
│       │   ├── synthesis_eval.py
│       │   ├── tool_eval.py
│       │   ├── schema_eval.py
│       │   ├── engineering_eval.py
│       │   ├── model_routing_eval.py
│       │   ├── privacy_eval.py
│       │   └── report.py
│       │
│       ├── trace/
│       │   ├── trace_logger.py
│       │   ├── trace_store.py
│       │   ├── trace_redactor.py
│       │   └── langsmith_adapter.py
│       │
│       ├── api/
│       │   ├── server.py
│       │   └── routes.py
│       │
│       └── cli/
│           ├── index.py
│           ├── ask.py
│           ├── synthesize.py
│           ├── digest.py
│           ├── topic.py
│           ├── write.py
│           ├── plan.py
│           ├── analyze.py
│           ├── eval.py
│           ├── trace.py
│           └── policy.py
│
├── eval_sets/
│   ├── rag_qa.jsonl
│   ├── citation.jsonl
│   ├── synthesis.jsonl
│   ├── tool_call.jsonl
│   ├── structured_output.jsonl
│   ├── engineering_analysis.jsonl
│   ├── model_routing.jsonl
│   └── privacy_routing.jsonl
│
├── sample_data/
│   ├── notes/
│   ├── docs/
│   ├── diffs/
│   ├── scan_findings/
│   └── expected_outputs/
│
├── examples/
│   ├── demo_local_fast.md
│   ├── demo_model_routing.md
│   ├── demo_privacy_gate.md
│   ├── demo_trace.md
│   └── demo_eval_report.md
│
├── data/
│   ├── lancedb/
│   ├── sqlite/
│   ├── traces/
│   ├── reports/
│   └── generated/
│
├── apps/
│   ├── web/
│   └── cli/
│
├── tests/
└── scripts/
    ├── check_local_llm.sh
    ├── check_langchain_llama_cpp.py
    ├── index_all.py
    ├── run_eval.py
    ├── export_report.py
    └── benchmark_models.py
```

---

## 20. Public / Private Data Strategy

### 20.1 Public Repo 可公開

1. framework code
2. sample notes
3. sample eval sets
4. fake scan findings
5. fake diffs
6. architecture docs
7. screenshots
8. README
9. eval report sample
10. trace sample
11. redacted config examples

---

### 20.2 Private Data 不公開

1. 完整個人筆記
2. 公司資料
3. 真實 code / diff
4. 真實 scan finding
5. 私人工作紀錄
6. API keys
7. 真實 trace
8. 真實 meeting notes
9. 真實工作提案草稿
10. 真實內部 log

---

### 20.3 Public Demo Strategy

建立假資料：

```text
sample_data/notes/
sample_data/diffs/
sample_data/scan_findings/
sample_data/expected_outputs/
```

公開 repo 展示功能，但不公開真實資料。

所有 sample data 必須標示：

```text
This is synthetic sample data for demonstration only.
```

---

## 21. README First Screen

```md
# Personal R&D Agent OS

A model-agnostic LangChain/LangGraph-based agent platform for personal research memory, RAG, technical writing, project planning, engineering analysis, and evaluation-driven AI workflows.

## Highlights

- LangGraph-based stateful workflow runtime
- Model routing across local llama.cpp models and stronger cloud/code models
- Privacy-aware routing for local-first personal knowledge workflows
- Effective privacy calculation across query, retrieved chunks, tool results, and memory context
- Citation-grounded RAG over Markdown research notes
- Research synthesis, daily research digests, topic exploration, technical writing, and project planning workflows
- Permission-gated tool execution with human-in-the-loop support
- Tool capability boundaries for local file and shell operations
- Structured outputs with schema validation
- Trace logging and evaluation harnesses
- Local-first design with optional cloud model escalation
- Release gates for RAG, citation, structured output, model routing, privacy, and tool permission

## Core Idea

This project is not a chatbot. It is a personal R&D operating layer that turns research notes, engineering context, and project decisions into a searchable, executable, traceable, and measurable AI-assisted workflow.
```

---

## 22. Resume / Portfolio Positioning

### 22.1 中文履歷

```text
Personal R&D Agent OS：以 LangChain v1 / LangGraph v1 建立模型無關的個人研發 Agent Runtime，整合本地 llama.cpp、雲端模型路由、隱私分級、引用式 RAG、工具權限控管、structured output、trace logging 與 evaluation harness。系統可索引個人研究筆記並支援研究問答、主題整理、每日摘要、技術寫作、專案規劃與工程分析；透過 RAG recall、citation accuracy、schema validity、model routing accuracy 與 privacy compliance 指標持續追蹤品質。
```

---

### 22.2 English Resume

```text
Built a model-agnostic Personal R&D Agent OS with LangChain v1 and LangGraph v1, integrating local llama.cpp inference, cloud model routing, privacy-aware routing, citation-grounded RAG, permission-gated tools, structured outputs, trace logging, and evaluation harnesses. The system turns personal research notes and engineering context into measurable workflows for research memory, synthesis, daily digests, technical writing, and project planning, with regression metrics for RAG recall, citation accuracy, schema validity, model routing, and privacy compliance.
```

---

### 22.3 LinkedIn Version

```text
I built a model-agnostic Personal R&D Agent OS using LangChain, LangGraph, llama.cpp, and multi-model routing. The system turns personal research notes and engineering context into a searchable, executable, and measurable AI-assisted workflow, supporting citation-grounded RAG, daily research digests, technical writing, project planning, tool permission control, trace logging, privacy-aware routing, and evaluation-driven optimization.
```

---

## 23. Success Criteria

### 23.1 Product Success

1. 日常真的會用
2. 能查回自己過去的研究資料
3. 能生成可用的 digest / summary / planning doc
4. 能幫助準備週報 / 簡報 / 提案
5. 能持續新增資料並更新索引
6. 能依 privacy level 正確選擇模型
7. 能避免 private_raw / company_sensitive 資料外洩
8. 能在 trace 裡看到每次執行的完整決策
9. 能用 eval report 持續改善品質

---

### 23.2 Engineering Success

1. 支援 LangGraph StateGraph workflow
2. 支援 checkpoint-based persistence
3. 支援多模型 routing
4. 支援 effective privacy routing
5. 支援 citation-grounded RAG
6. 支援 citation validation
7. 支援 structured output validation
8. 支援 permission-gated tool execution
9. 支援 tool capability boundary
10. 支援 local trace logging
11. 支援 regression eval
12. 支援 release gate
13. 支援 local + cloud hybrid runtime
14. 支援 llama.cpp + LangChain compatibility tests

---

### 23.3 Portfolio Success

1. GitHub repo 看得出架構完整
2. README 有清楚定位
3. 有架構圖
4. 有 CLI demo
5. 有 Web UI screenshot
6. 有 eval report sample
7. 有 trace sample
8. 有 model routing 文件
9. 有 privacy routing 文件
10. 有 permission gate 文件
11. 有 tool capability boundary 文件
12. 有 LangChain / llama.cpp compatibility 文件
13. 有 resume case study
14. 有 sample data，不公開真實資料

---

## 24. v1 Complete Execution Scope

### 24.1 v1 必須完成的完整閉環

v1 不追求把所有 App 都做成大型產品，而是要完成一條完整、可展示、可評估、可持續優化的 R&D Agent workflow。

完整閉環：

```text
Markdown notes
→ index
→ retrieve
→ cite
→ calculate effective privacy
→ route model
→ generate
→ validate structured output
→ validate citations
→ save trace
→ run eval
→ show metrics
```

---

### 24.2 v1 Core Deliverables

v1 必須交付：

1. Markdown notes indexing
2. YAML frontmatter parsing
3. heading-aware chunking
4. LanceDB vector search
5. SQLite metadata store
6. SQLite FTS5 keyword search
7. Hybrid retrieval
8. Research Memory Agent
9. Model Router
10. Privacy Router
11. Effective Privacy Calculator
12. Citation Builder
13. Citation Validator
14. Structured Output Formatter
15. Local Trace Store
16. RAG Eval
17. Citation Eval
18. Model Routing Eval
19. Privacy Policy Eval
20. CLI demo
21. Trace Viewer
22. Eval Dashboard
23. Sample public dataset
24. README demo

---

### 24.3 v1 Demo Flow

```bash
rdos index ./sample_data/notes

rdos ask "我之前是不是看過一篇講 RAG 是 filtering 的文章？"

rdos trace show <run_id>

rdos eval all
```

System flow：

```text
user query
→ classify task
→ assess query privacy
→ retrieve notes
→ aggregate retrieved chunk privacy
→ calculate effective privacy level
→ select model profile
→ generate answer
→ validate citations
→ format structured output
→ save trace
→ run eval
```

---

### 24.4 v1 Completion Criteria

v1 完成標準：

1. 可以索引 sample Markdown notes
2. 可以回答 research memory 類問題
3. 回答必須附 citation
4. citation 必須能映射回 chunk
5. trace 中可看到 model routing decision
6. trace 中可看到 privacy decision
7. trace 中可看到 effective privacy level
8. structured output 必須通過 Pydantic validation
9. 至少有 20 筆 RAG eval dataset
10. 至少有 20 筆 model routing eval dataset
11. 至少有 20 筆 privacy routing eval dataset
12. privacy policy compliance 必須達 100%
13. README 可以展示 CLI output、trace sample、eval report
14. release gate 必須通過

---

## 25. Final Decision

Personal R&D Agent OS 的核心價值不是某顆模型，而是建立一套可持續演進的個人 AI engineering platform。

最終定位：

```text
一套模型無關、隱私感知、可追蹤、可評估的個人研發 Agent 作業系統。
```

核心能力：

```text
Research Memory
Research Synthesis
Daily Digest
Topic Explorer
Technical Writing
Project Planning
Engineering Analysis
Model Routing
Privacy Routing
Tool Permission
Structured Output
Trace
Evaluation
```

技術主軸：

```text
LangChain v1
LangGraph v1
llama.cpp
Multi-model routing
Privacy-aware routing
Effective privacy calculation
Citation-grounded RAG
Structured output
Permission-gated tools
Tool capability boundary
Trace / Eval
Release gates
```

本專案最適合你的原因：

1. 你已經有大量高品質研究資料
2. 你工作需要大量技術整理與 AI engineering 判斷
3. 你已有本地模型與 Agent 實測基礎
4. 你需要可持續優化、可放履歷、可反哺工作的 side project
5. 這個專案不會被任何單一模型淘汰

最終一句話：

```text
Personal R&D Agent OS 是把你的研究資料、工程經驗、技術判斷與日常輸出流程，變成一套可查詢、可執行、可追蹤、可評估、可長期升級的 AI Agent 系統。
```

