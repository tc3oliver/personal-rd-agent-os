# Batch 12：Real Research Corpus Ingestion

## 目標

讓 RDOS 真正吃 clawd-research 研究筆記庫。不是盲目 index 全部 2,088 篇，而是做出**可控、可增量、可觀測、可回滾**的真實資料 ingestion pipeline。

## 背景

資料來源：`~/Workspace/notes/AI/clawd-research/`
- 2,088 markdown files
- 25 topic folders
- latest: 2026-07
- 檔名前綴多為 YYMMDD
- 預設 `private_raw`，不可送外部模型

## Agent 任務

### 1. CLI

支援大型資料夾 + corpus preset：

```bash
# 通用
rdos index ~/Workspace/notes/AI/clawd-research \
  --embedding-provider local-bge-m3 \
  --privacy-default private_raw \
  --source-collection clawd-research

# Preset
rdos index-corpus clawd-research --scope rag       --embedding-provider local-bge-m3
rdos index-corpus clawd-research --scope agent     --embedding-provider local-bge-m3
rdos index-corpus clawd-research --scope eval      --embedding-provider local-bge-m3
rdos index-corpus clawd-research --scope security  --embedding-provider local-bge-m3
rdos index-corpus clawd-research --scope devtools  --embedding-provider local-bge-m3
rdos index-corpus clawd-research --scope all       --embedding-provider local-bge-m3
```

Preset 對應：

| scope | folder |
| --- | --- |
| `rag` | 知識與檢索 |
| `agent` | AI代理系統 |
| `eval` | LLM推理與評估 |
| `security` | AI安全 |
| `devtools` | 開發者工具與框架 |
| `all` | 全部 |

### 2. Incremental Index

| 檔案狀態 | 行為 |
| --- | --- |
| new | insert |
| modified (content_hash變) | reindex |
| unchanged | skip |
| missing (檔案已刪) | mark `stale=true` |

不可每次重建全部。

### 3. Frontmatter 不完整也要能處理

| 欄位 | 缺失時的策略 |
| --- | --- |
| `title` | 從 H1 或 filename 推導 |
| `date` | 從 filename YYMMDD 推導 |
| `tags` | `[]` |
| `privacy_level` | 使用 `--privacy-default`（預設 `private_raw`） |
| `source_collection` | 從 CLI 參數或路徑推導 |

### 4. Topic / Folder Metadata

從 folder name 推導：

```json
{
  "folder": "知識與檢索",
  "topic": "知識與檢索",
  "source_collection": "clawd-research"
}
```

### 5. SQLite Schema 擴充

`documents` 表加入：

- `source_collection`
- `topic`
- `indexed_at`
- `stale` (boolean)
- `last_modified` (file mtime)

### 6. Index Report

每次 index 完產生 `data/reports/index_report_<timestamp>.md`，包含：

- indexed documents
- generated chunks
- skipped unchanged
- updated documents
- stale documents
- privacy distribution（依 level 統計）
- topic distribution（依資料夾統計）
- embedding provider / model / dim
- errors
- slowest files（top 10 by latency）

## 需求

1. `rdos index` 支援大型資料夾。
2. 新增 `--source-collection` 參數。
3. 新增 `--privacy-default private_raw` 參數。
4. frontmatter 缺 title → 從 H1 或 filename 推導。
5. frontmatter 缺 date → 從 filename YYMMDD 推導。
6. frontmatter 缺 tags → 使用 `[]`。
7. frontmatter 缺 privacy_level → 使用 `--privacy-default`。
8. 從 folder name 推導 topic / folder metadata。
9. 支援 incremental index（unchanged skip / modified reindex / new insert / missing mark stale）。
10. SQLite metadata 加入 `source_collection`、`topic`、`indexed_at`、`stale` 欄位。
11. 每次 index 產生 `data/reports/index_report_<timestamp>.md`。
12. index report 包含上列 10 項。
13. 新增 corpus preset（rag / agent / eval / security / devtools / all）。
14. preset 對應如上表。
15. **不要把 `~/Workspace/notes` 路徑寫死在程式碼**，要可由 config 或 CLI 傳入。
16. tests 使用 temporary sample corpus，不依賴真實 clawd-research 路徑。
17. README 補上 real corpus ingestion 範例。

## 驗收

```bash
uv run pytest
uv run ruff check .

# 先跑三個高相關 scope
uv run rdos index-corpus clawd-research --scope rag   --embedding-provider local-bge-m3
uv run rdos index-corpus clawd-research --scope agent --embedding-provider local-bge-m3
uv run rdos index-corpus clawd-research --scope eval  --embedding-provider local-bge-m3

# 搜尋驗證
uv run rdos search "GraphRAG VectorRAG 層次化摘要"        --embedding-provider local-bge-m3
uv run rdos search "AgentTrace 多智能體因果圖追蹤"        --embedding-provider local-bge-m3
uv run rdos search "Argus LLM 六維度輸出評估框架"          --embedding-provider local-bge-m3
```

## 完成後輸出

1. 修改檔案
2. corpus ingestion 流程
3. incremental index 策略
4. index report 範例
5. 驗收結果
6. 下一個建議 batch

## Commit

```
feat(batch-12): ingest real clawd research corpus
```
