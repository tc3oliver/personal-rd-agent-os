# Batch 2：Markdown Parser + Heading-aware Chunker

## 目標

把 Markdown 筆記轉成可 index 的 chunks。

## Agent 任務

請實作 Markdown parser 與 heading-aware chunker。

新增檔案：

- `src/rdos/rag/markdown_parser.py`
- `src/rdos/rag/chunker.py`
- `tests/test_markdown_parser.py`
- `tests/test_chunker.py`
- `sample_data/notes/*.md`（5 篇 synthetic sample notes）

## 需求

1. 支援 YAML frontmatter。
2. 從 frontmatter 讀取：
   - `title`
   - `date`
   - `tags`
   - `privacy_level`
3. 如果 frontmatter 沒有 `privacy_level`，預設為 `private_raw`。
4. 依 Markdown heading 切分 chunk。
5. 每個 chunk 保留 `heading_path`（從 root 到當前 heading 的完整路徑）。
6. chunk 目標 300~600 tokens，可用簡化 token estimator（例如 `len(text) // 4`）。
7. 每個 chunk 必須包含：
   - `doc_id`
   - `file_path`
   - `title`
   - `heading_path`
   - `chunk_id`
   - `chunk_text`
   - `token_count`
   - `content_hash`
   - `chunk_hash`
   - `privacy_level`
8. `content_hash` 使用全文 hash。
9. `chunk_hash` 使用 `chunk_text + metadata` hash。
10. 加入 5 篇 synthetic sample markdown notes，涵蓋：
    - 不同 privacy_level
    - 不同 tags
    - 多層 heading 結構
    - 中英文混雜內容
    - 至少一篇明確標記 `company_sensitive`

## 限制

- 不要接 LanceDB
- 不要接 LLM

## 驗收

```bash
uv run pytest tests/test_markdown_parser.py
uv run pytest tests/test_chunker.py
```

## 檢查清單

- [ ] 每個 chunk 都有 `heading_path`
- [ ] 每個 chunk 都有 `privacy_level`
- [ ] 每個 chunk 都有 `chunk_hash`
- [ ] 沒有 `privacy_level` 的檔案預設為 `private_raw`
- [ ] heading 路徑正確反映巢狀結構（例如 `["RAG", "Filtering", "Chunking"]`）
- [ ] chunk token 數落在 300~600 區間（少數邊界 chunk 可例外）

## 範例 Sample Note

```markdown
---
title: RAG Filtering 筆記
date: 2026-06-30
tags: [rag, retrieval, filtering]
privacy_level: private_raw
---

# RAG Filtering

## 為什麼需要 Filtering

 retrieved chunks 雜訊過多會稀釋 context...

## 主要策略

### Metadata Filter

先依 tag、date 過濾...

### Semantic Filter

用 embedding 相似度做 second-stage filter...
```

## 介面參考

```python
from rdos.rag.markdown_parser import parse_markdown_file
from rdos.rag.chunker import chunk_document

doc = parse_markdown_file("sample_data/notes/rag_filtering.md")
chunks = chunk_document(doc)
```
