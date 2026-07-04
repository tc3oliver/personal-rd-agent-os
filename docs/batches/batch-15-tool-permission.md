# Batch 15：Runtime Tool Permission + Safe File Tools

## 目標

把 `tool_policy.yaml` 從文件變成 runtime enforcement。建立 `ToolRegistry` / `PermissionGate` / `CapabilityBoundary`，並實作 safe file tools。

## 範圍限制

**只做 safe tools**：

- `search_notes`
- `read_note`
- `list_recent_notes`
- `export_report`

**不做危險工具**：

- `run_shell`
- `git_push`
- `send_email`
- `delete_file`

## Agent 任務

### 1. Tool Registry

新增模組：

- `src/rdos/tools/registry.py`
- `src/rdos/tools/permission_gate.py`
- `src/rdos/tools/capability_boundary.py`
- `src/rdos/tools/knowledge_tools.py`
- `src/rdos/tools/export_tools.py`

從 `configs/tool_policy.yaml` 讀取：

- `tool_name`
- `permission_level`
- `allowed_roots`
- `blocked_patterns`
- `max_bytes`
- `requires_approval`

### 2. Capability Boundary（安全防線）

`read_note` 必須 enforce：

- path must be inside `allowed_roots`
- block `.env` / credentials / secrets / `id_rsa`
- block path traversal（`../`）
- block symlink escaping `allowed_roots`
- enforce `max_bytes`

### 3. Permission Decision

每個 tool call 都產生：

```json
{
  "tool_name": "read_note",
  "permission_level": "low",
  "allowed": true,
  "requires_approval": false,
  "reason": "path is within allowed notes root"
}
```

### 4. Medium-risk Approval

`export_report` 若 `requires_approval=true`：

- 先回 `approval_required`
- 不直接寫檔
- **不做完整 HITL UI**（這批只回 decision）

### 5. Trace Integration

trace 加入：

```json
{
  "permission_decisions": [
    {"tool_name": "read_note", "allowed": true, "reason": "..."},
    {"tool_name": "export_report", "allowed": false, "requires_approval": true}
  ]
}
```

### 6. CLI

可選新增：

```bash
rdos tool read-note <path>
rdos tool policy-check <tool_name> --arg ...
```

## 需求

1. 實作 `ToolRegistry` / `PermissionGate` / `CapabilityBoundary`。
2. 從 `configs/tool_policy.yaml` 讀取 policy。
3. 實作 safe tools：`search_notes` / `read_note` / `list_recent_notes` / `export_report`。
4. `read_note` enforce：`allowed_roots` / block secrets / block traversal / block symlink escape / `max_bytes`。
5. `export_report` 若 `requires_approval=true`，回傳 `approval_required`，不寫檔。
6. Trace 記錄 `permission_decisions`。
7. `rdos tool read-note <path>` 與 `rdos tool policy-check <tool_name> --arg ...` 至少支援。
8. tests 必須覆蓋：
   - allowed `read_note` 通過
   - blocked `.env` 被拒絕
   - path traversal 被拒絕
   - symlink escape 被拒絕
   - `max_bytes` 超過被拒絕
   - `export_report` requires approval
9. **不要實作** `run_shell` / `git_push` / `send_email` / `delete_file`。
10. README 補上 tool permission 設計摘要。

## 驗收（必過安全檢查）

```bash
uv run pytest
uv run ruff check .

# 應該通過
uv run rdos tool read-note sample_data/notes/rag_filtering.md

# 應該被拒絕
uv run rdos tool read-note .env

# 應該回 approval_required
uv run rdos tool policy-check export_report
```

## 驗收重點

這批重點是**安全，不是功能多**。必過：

- `.env` 被拒絕
- `../` path traversal 被拒絕
- symlink escape 被拒絕

## 完成後輸出

1. 修改檔案
2. tool registry 架構
3. permission gate 決策流程
4. capability boundary 防護
5. 驗收結果
6. 下一個建議 batch

## Commit

```
feat(batch-15): enforce runtime tool permission gate
```
