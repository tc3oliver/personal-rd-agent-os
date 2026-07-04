# Batch 1：Schema + Config Loader

## 目標

先把資料契約固定下來。

## Agent 任務

請實作 RDOS 的 schema 與 config loader。

新增檔案：

- `src/rdos/schemas/document.py`
- `src/rdos/schemas/citation.py`
- `src/rdos/schemas/privacy.py`
- `src/rdos/schemas/routing.py`
- `src/rdos/schemas/research.py`
- `src/rdos/schemas/trace.py`
- `src/rdos/config.py`

## 需求

1. 使用 Pydantic 定義以下 schema：
   - `DocumentChunk`
   - `Citation`
   - `CitationValidationResult`
   - `PrivacyDecision`
   - `ModelRoutingDecision`
   - `ResearchAnswer`
   - `TraceRecord`

2. 所有 schema key 使用英文。

3. Privacy level 支援以下四個等級（由低到高）：
   - `public`
   - `private_summary`
   - `private_raw`
   - `company_sensitive`

4. Config loader 可以讀取：
   - `configs/models.yaml`
   - `configs/privacy_policy.yaml`
   - `configs/rag.yaml`
   - `configs/tool_policy.yaml`

5. 加入基本 unit tests。

## 限制

- 不要實作 LLM
- 不要實作 RAG
- 只做 schema 與 config

## 驗收

```bash
uv run pytest tests/
```

測試輸出必須包含：

```
schema validation passed
config loader passed
```

## Schema 細節參考

### `DocumentChunk`

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `doc_id` | `str` | 文件唯一 ID |
| `file_path` | `str` | 原始檔案路徑 |
| `title` | `str` | 文件標題 |
| `heading_path` | `list[str]` | 從 root 到當前 heading 的路徑 |
| `chunk_id` | `str` | chunk 唯一 ID |
| `chunk_text` | `str` | chunk 內容 |
| `token_count` | `int` | 估計 token 數 |
| `content_hash` | `str` | 全文 hash |
| `chunk_hash` | `str` | chunk + metadata hash |
| `privacy_level` | `PrivacyLevel` | 隱私等級 |

### `Citation`

| 欄位 | 型別 |
| --- | --- |
| `chunk_id` | `str` |
| `doc_id` | `str` |
| `file_path` | `str` |
| `title` | `str` |
| `heading_path` | `list[str]` |
| `quote` | `str` |
| `chunk_hash` | `str` |

### `ModelRoutingDecision`

| 欄位 | 型別 |
| --- | --- |
| `task_type` | `str` |
| `risk_level` | `str` |
| `effective_privacy_level` | `PrivacyLevel` |
| `selected_profile` | `str` |
| `provider` | `str` |
| `requires_user_confirmation` | `bool` |
| `reason` | `str` |

## Config Loader 介面參考

```python
from rdos.config import load_config

config = load_config()  # 讀取所有 configs/*.yaml
config.models          # models.yaml
config.privacy_policy  # privacy_policy.yaml
config.rag             # rag.yaml
config.tool_policy     # tool_policy.yaml
```
