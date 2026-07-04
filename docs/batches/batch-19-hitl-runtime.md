# Batch 19：HITL Approval Runtime（v0.2 Trust Runtime 第一批）

## 目標

把 Batch 15 的 `approval_required` 從「決策」變成「真正可 approve / deny 的流程」。讓 RDOS 的 permission gate **閉環**。

## 為什麼是 v0.2 第一批

Permission gate 已經有 runtime enforcement（Batch 15），但 `export_report` 等 `requires_approval` 工具目前只能：

1. 回 `approval_required`
2. **不寫檔**

這代表工具實際上不能完成任務。v0.2 必須補上 approve/deny 流程。

## Agent 任務

### 1. LangGraph interrupt / resume

- 用 `langgraph.types.interrupt()` 在 approval node 暫停
- 用 `Command(resume=...)` 在 approval 後恢復
- checkpointer 從 InMemorySaver 升級到 `langgraph-checkpoint-sqlite`

### 2. Approval Queue

新增：

- `src/rdos/approvals/queue.py` — SQLite-backed approval queue
- `src/rdos/approvals/models.py` — `ApprovalRequest` schema
- `data/approvals.db` — 持久化

每個 approval request 包含：

```json
{
  "approval_id": "uuid",
  "run_id": "trace run_id",
  "thread_id": "langgraph thread_id",
  "tool_name": "export_report",
  "args": {"target_path": "...", "content": "..."},
  "requested_at": "ISO 8601",
  "decided_at": null,
  "decision": null,
  "decided_by": null,
  "idempotency_key": "sha256(...)"
}
```

### 3. CLI

```bash
rdos approval list                       # pending 列表
rdos approval show <approval_id>         # 完整 request
rdos approval approve <approval_id>      # 通過 + resume graph
rdos approval deny <approval_id> [reason]# 拒絕 + graph 結束
```

### 4. Replay Protection

- `idempotency_key = sha256(run_id + tool_name + args)` — 重複 approve 不會重跑工具
- Approval 一旦決定就 immutable

### 5. export_report 閉環

- Approval 通過 → graph resume → 寫檔
- Approval 拒絕 → graph resume 到 denied node → 不寫檔
- 沒 approval 的 export → 永遠卡在 interrupt

## 需求

1. LangGraph 用 `interrupt()` 在 approval node 暫停。
2. SQLite checkpointer 持久化 thread state（重啟後可 resume）。
3. Approval queue 是獨立 SQLite（`data/approvals.db`），不混在 trace jsonl。
4. Idempotency key 防重複 approve。
5. CLI list/show/approve/deny 四個指令。
6. approve 後 graph 自動 resume 並執行 tool。
7. deny 後 graph 結束、tool 不執行、trace 記錄 deny reason。
8. tests 必須覆蓋：
   - interrupt 觸發
   - resume 後 tool 執行
   - replay protection（同 approval_id approve 兩次只執行一次）
   - denied 路徑
9. trace 必須記錄 approval_id / decision / decided_by。

## 驗收

```bash
uv run pytest
uv run ruff check .

# 真實流程 demo
uv run rdos research synthesize "..." \
  --embedding-provider local-bge-m3
# → 觸發 export_report → 卡在 approval

uv run rdos approval list
# → 看到 pending approval

uv run rdos approval approve <id>
# → graph resume → 報告寫到 data/generated/reports/

uv run rdos approval approve <id>
# → replay blocked (idempotency)
```

## 完成後輸出

1. 修改檔案
2. interrupt/resume 流程圖
3. approval queue schema
4. idempotency 機制
5. 驗收結果
6. 下一個建議 batch

## Commit

```
feat(batch-19): hitl approval runtime with langgraph interrupt
```
