# Batch 8：Trace Store

## 目標

每次執行都要可追蹤。

## Agent 任務

請實作 local trace store。

新增檔案：

- `src/rdos/trace/trace_logger.py`
- `src/rdos/trace/trace_store.py`
- `src/rdos/cli/trace.py`

## 需求

1. 每次 `rdos ask` 都寫入 trace。
2. trace 使用 **JSONL** 儲存在 `data/traces/runs.jsonl`。
3. trace 內容包含：

   | 欄位 | 說明 |
   | --- | --- |
   | `run_id` | 唯一 run ID（uuid） |
   | `timestamp` | ISO 8601 |
   | `task_type` | e.g. `research_memory` |
   | `user_query` | 原始 query |
   | `privacy_decision` | `PrivacyDecision` |
   | `effective_privacy_level` | 最終 privacy level |
   | `model_routing_decision` | `ModelRoutingDecision` |
   | `retrieved_docs` | list of doc / chunk metadata |
   | `citations` | list of `Citation` |
   | `citation_validation_result` | `CitationValidationResult` |
   | `final_answer` | `ResearchAnswer` |
   | `structured_output` | 最終結構化輸出 |
   | `metrics` | latency、token usage 等 |
   | `errors` | 過程中任何錯誤 |

4. CLI 支援：

   ```
   rdos trace list
   rdos trace show <run_id>
   ```

5. 加入 tests。

## 驗收

```bash
uv run rdos ask "RAG filtering 是什麼？"
uv run rdos trace list
uv run rdos trace show <run_id>
```

## Trace Store 介面參考

```python
class TraceStore(Protocol):
    def append(self, record: TraceRecord) -> None: ...
    def list_runs(self, limit: int = 20) -> list[TraceRecord]: ...
    def get(self, run_id: str) -> TraceRecord | None: ...

class JsonlTraceStore(TraceStore):
    def __init__(self, path: str = "data/traces/runs.jsonl"): ...
```

## CLI 行為

### `rdos trace list`

```
run_id        timestamp                  task_type          privacy           model
abc123...     2026-07-04T10:00:00Z       research_memory    private_raw       local_fast
def456...     2026-07-04T09:30:00Z       research_memory    private_summary   cloud_reasoning
```

### `rdos trace show <run_id>`

完整 JSON dump，包含所有欄位。

## 檢查清單

- [ ] 每次 `rdos ask` 都會 append 一筆 trace
- [ ] JSONL 每行一筆 record，可獨立 parse
- [ ] `trace list` 至少顯示 5 個摘要欄位
- [ ] `trace show <run_id>` 顯示完整 record
- [ ] 沒有實作 LLM 也能寫入 trace（metrics / errors 可為空）
- [ ] 同一 run 不會重複寫入
