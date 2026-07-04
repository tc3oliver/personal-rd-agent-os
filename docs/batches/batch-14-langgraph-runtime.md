# Batch 14：LangGraph Runtime + Checkpoint Trace

## 目標

把目前 linear runner 升級成正式 LangGraph runtime，補上 checkpoint、thread_id、node-level trace，為後續 HITL（human-in-the-loop）打基礎。

## Agent 任務

### 1. LangGraph StateGraph

正式節點（11 + 1 trace）：

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
11. `save_trace`

使用 `langgraph.graph.StateGraph(ResearchGraphState)`，每個 node 是 `(state) -> state` 的純函式。

### 2. Checkpointer

| 用途 | 實作 |
| --- | --- |
| dev / test | `InMemorySaver` |
| 預留 | `SQLiteCheckpointer` interface（可後續接 LangGraph 官方 sqlite saver） |

### 3. Node-level Trace

trace 必須能看到：

```json
{
  "graph_runtime": "langgraph",
  "thread_id": "...",
  "nodes": [
    {
      "name": "retrieve_notes",
      "status": "success",
      "latency_ms": 120,
      "inputs_summary": {"query": "..."},
      "outputs_summary": {"retrieved_count": 5}
    },
    {
      "name": "generate_answer",
      "status": "success",
      "latency_ms": 1842,
      "inputs_summary": {"context_len": 4096},
      "outputs_summary": {"answer_len": 512}
    }
  ]
}
```

### 4. CLI

```bash
# 預設 langgraph
rdos ask "..."

# 顯式指定
rdos ask "..." --graph-runtime langgraph
rdos ask "..." --graph-runtime linear
```

## 需求

1. 使用 LangGraph `StateGraph` 定義上列 11 + 1 個節點。
2. state 使用現有 `ResearchGraphState` 或合理重構後的 TypedDict。
3. `root_graph.py` 改成呼叫 compiled graph（`graph.compile(checkpointer=...)`）。
4. 保留 linear runner 作為 legacy fallback 或 test helper。
5. `rdos ask` 新增 `--graph-runtime langgraph|linear`，預設 `langgraph`。
6. 加入 checkpointer：dev/test 用 `InMemorySaver`，預留 SQLite checkpointer interface。
7. 每次 run 必須有 `thread_id`（uuid4 hex）。
8. trace 必須記錄 `graph_runtime` / `thread_id` / node sequence / 每個 node latency / node status / error if any。
9. 保留現有 CLI 輸出格式（Answer / Citations / Routing 三個 panel）。
10. **不改** retrieval / privacy / model router 邏輯。
11. tests 必須覆蓋：
    - langgraph invoke success
    - state 欄位完整
    - trace 中有 `graph_runtime=langgraph`
    - linear fallback 仍可用

## 驗收

```bash
uv run pytest
uv run ruff check .

uv run rdos ask "我有沒有整理過 AgentTrace？" \
  --graph-runtime langgraph \
  --llm-mode local \
  --embedding-provider local-bge-m3

uv run rdos trace show <run_id>
```

trace 必須看到：

- `graph_runtime = langgraph`
- `thread_id`
- node-level trace（含每個節點 latency 與 status）
- model routing decision
- privacy decision
- citation validation result

## 完成後輸出

1. 修改檔案
2. LangGraph graph 結構
3. checkpoint 設計
4. trace 變更
5. 驗收結果
6. 下一個建議 batch

## Commit

```
feat(batch-14): migrate research workflow to langgraph runtime
```
