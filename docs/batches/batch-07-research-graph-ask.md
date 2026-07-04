# Batch 7：Research Memory Graph + Ask CLI

## 目標

做出第一條完整 agent workflow。

## Agent 任務

請實作 Research Memory Graph 與 `ask` CLI。

新增檔案：

- `src/rdos/graph/state.py`
- `src/rdos/graph/research_memory_graph.py`
- `src/rdos/graph/root_graph.py`
- `src/rdos/cli/ask.py`

## 需求

`rdos ask "question"` 執行以下流程（LangGraph StateGraph）：

1. `classify_task`
2. `assess_query_privacy`
3. `retrieve_notes`
4. `calculate_effective_privacy`
5. `select_model_profile`
6. `build_context`
7. `generate_answer`
8. `build_citations`
9. `validate_citations`
10. `format_structured_output`
11. `return answer`

第一版只支援 `research_memory` task type。

## 輸出規格

輸出必須包含：

1. `answer`
2. `citations`
3. `confidence`
4. `selected_model_profile`
5. `effective_privacy_level`

## 限制

- 第一版只支援 `research_memory`
- 不要做 Web UI
- 不要在 ModelRouter 裡 bind_tools

## 驗收

```bash
uv run rdos ask "我之前是不是看過一篇講 RAG filtering 的文章？"
```

預期輸出：

```
Answer:
<答案內文>

Citations:
- file: sample_data/notes/rag_filtering.md
  heading_path: ["RAG Filtering", "主要策略", "Semantic Filter"]
  chunk_id: <uuid>

Model: local_fast

Privacy: private_raw
```

## Graph State 參考

```python
class ResearchGraphState(TypedDict):
    user_query: str
    task_type: str
    query_privacy_level: PrivacyLevel
    retrieved_chunks: list[DocumentChunk]
    effective_privacy_level: PrivacyLevel
    model_routing: ModelRoutingDecision
    context: str
    raw_answer: str
    citations: list[Citation]
    citation_validation: CitationValidationResult
    final_answer: ResearchAnswer
```

## 介面參考

```python
from rdos.graph.research_memory_graph import build_research_memory_graph

graph = build_research_memory_graph(...)
result = graph.invoke({"user_query": "..."})
```

## 檢查清單

- [ ] graph 包含 11 個 node
- [ ] node 之間 state 流轉正確
- [ ] 輸出含 5 個必要欄位
- [ ] privacy_level 與 model profile 一致（不會 private_raw 卻走 cloud）
- [ ] citations 全部通過 `CitationValidator`
- [ ] 沒有 Web UI
