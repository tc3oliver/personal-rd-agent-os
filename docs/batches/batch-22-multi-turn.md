# Batch 22：Multi-turn Research Thread（v0.2 Trust Runtime 第四批）

## 目標

從單次問答進化成真正的研究助理 — 可以追問、引用前幾輪、不會無限膨脹 context。

## 背景

Batch 14 已經有 LangGraph StateGraph + thread_id + checkpointer，但每個 `rdos ask` 都是獨立的。v0.2 最後一批要把它串起來。

## Agent 任務

### 1. Thread State

`rdos thread` CLI：

```bash
rdos thread new                              # 建立 thread，回 thread_id
rdos thread ask <thread_id> "follow-up..."   # 在 thread 內追問
rdos thread list                             # 列出最近 threads
rdos thread show <thread_id>                 # 完整對話
rdos thread close <thread_id>                # 結束 thread
```

Thread state 包含：

```python
class ThreadState(TypedDict):
    thread_id: str
    created_at: str
    closed_at: str | None
    turns: list[TurnRecord]
    cited_chunks: set[str]    # carry-forward
    compressed_summary: str   # memory compression
```

### 2. Follow-up Query Rewrite

每個 follow-up query 先過 rewrite：

- 把 "他" / "這個" / "上述" 解析成前輪實體
- 接續前輪的時間 / 範圍
- 用 LLM 或 rule-based

範例：

```
Turn 1: AgentTrace 是什麼？
Turn 2: 它跟 flight recorder 有什麼關係？
        → rewritten: "AgentTrace 跟 flight recorder 有什麼關係？"
```

### 3. Cited Context Carry-forward

Thread 內所有 cited chunks 累積成「已知事實」：

- 下輪檢索時這些 chunks 加權
- 引用編號延續（[1] 還是 [1]）
- 避免「前面講過，後面又檢索一次」

### 4. Stale Context Detection

Thread 跨多次 ask 時：

- 早期 chunk 可能已 reindex（chunk_hash 變）
- 用 `CitationValidator`（Batch 4）檢查 cited chunks 是否仍然 valid
- 失效 → 標 stale + 重新檢索

### 5. Conversation Trace

trace 補 `thread_id` 與 `turn_index`：

```json
{
  "run_id": "...",
  "thread_id": "...",
  "turn_index": 3,
  "previous_run_id": "..."
}
```

可重建完整對話時間軸。

### 6. Memory Compression

Thread 超過 N 輪（預設 5）時：

- 用 LLM 把前面輪摘要成 200 字
- 摘要取代原文進 context
- 釋出 context budget 給當前輪

### 7. Context Budget Management

```yaml
conversation:
  max_turns_in_context: 5
  max_total_tokens: 8000
  compression_strategy: summarize_oldest
  carry_forward_citations: true
```

每輪進 graph 前：

- 計算總 tokens（cited chunks + history + current query）
- 超出 budget → 觸發 compression
- 壓縮後仍超 → 拒絕（要求 close thread 重開）

## 需求

1. `rdos thread new/ask/list/show/close` 五個指令。
2. ThreadState 用 SQLite 持久化（`data/threads.db`）。
3. Follow-up rewriter 用 LLM 或 rule-based（v0.2 可先用 rule-based）。
4. Cited context carry-forward 必須跨輪延續編號。
5. Stale chunk 用 `CitationValidator` 檢查。
6. trace 補 `thread_id` / `turn_index` / `previous_run_id`。
7. Memory compression 在 N 輪後觸發。
8. tests 必須覆蓋：
   - thread 建立與 multi-turn ask
   - follow-up rewrite
   - cited context carry-forward
   - stale detection

## 驗收

```bash
uv run pytest
uv run ruff check .

# Multi-turn demo
TID=$(uv run rdos thread new)
uv run rdos thread ask $TID "AgentTrace 是什麼？"
uv run rdos thread ask $TID "它跟 flight recorder 有什麼不同？"
uv run rdos thread ask $TID "可以舉實際案例嗎？"
uv run rdos thread show $TID
# → 看到完整 3 輪對話 + 連續 citation 編號
```

## 完成後輸出

1. 修改檔案
2. Thread state schema
3. compression 流程
4. multi-turn demo 結果
5. 驗收結果
6. v0.2 release tag 計畫

## Commit

```
feat(batch-22): multi-turn research thread with cited context carry-forward
```

## v0.2 收尾

Batch 22 完成後：

```bash
git tag v0.2.0-trust-runtime
```

Release notes 寫在 `docs/release_notes/v0.2.0-trust-runtime.md`。
