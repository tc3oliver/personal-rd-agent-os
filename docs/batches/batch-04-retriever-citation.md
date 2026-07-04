# Batch 4：Hybrid Retriever + Citation Builder

## 目標

讓系統可以查回資料，而且能產生 citation。

## Agent 任務

請實作 hybrid retriever 與 citation builder。

新增檔案：

- `src/rdos/rag/retriever.py`
- `src/rdos/rag/hybrid_search.py`
- `src/rdos/rag/citation_builder.py`
- `src/rdos/rag/citation_validator.py`

## 需求

1. 支援 semantic search，從 LanceDB 搜尋。
2. 支援 keyword search，使用 SQLite FTS5（或簡化 LIKE search 起步）。
3. 合併 semantic results 與 keyword results：
   - 可採 RRF (Reciprocal Rank Fusion) 或加權分數
4. 支援 metadata filter：
   - `privacy_level`
   - `tags`
   - `date`（含 date range）
   - `folder`
5. `CitationBuilder` 從 retrieved chunk 建立 `Citation`：
   - 抽取 quote（chunk 中符合 query 的片段）
   - 帶入 doc metadata
6. `CitationValidator` 檢查：
   - `chunk_id` 是否存在於 SQLite
   - `chunk_hash` 是否一致
   - citation 是否來自 retrieved context（未被 LLM 幻覺偽造）
7. 加入 CLI：
   ```
   rdos search "query"
   ```
8. 加入 tests。

## 限制

- embedding 仍可使用 fake embedding
- 架構要能替換成真 embedding

## 驗收

```bash
uv run rdos search "RAG filtering"
```

預期輸出必須包含：

```
Top results:
- title: RAG Filtering 筆記
  heading_path: ["RAG Filtering", "主要策略", "Semantic Filter"]
  score: 0.83
  chunk_id: <uuid>
```

## Retriever 介面參考

```python
from rdos.rag.retriever import HybridRetriever, RetrievalRequest

retriever = HybridRetriever(...)
results = retriever.search(RetrievalRequest(
    query="RAG filtering",
    top_k=5,
    filters={"privacy_level": ["public", "private_summary"]},
))
```

## Citation Validator 規格

```python
class CitationValidator:
    def validate(
        self,
        citation: Citation,
        retrieved_chunks: list[DocumentChunk],
    ) -> CitationValidationResult: ...

# 必須回傳：
# - chunk_exists: bool
# - hash_matches: bool
# - in_retrieved_context: bool
# - is_valid: bool  # 以上三者 AND
```

## 檢查清單

- [ ] semantic + keyword 結果有合併機制
- [ ] metadata filter 至少支援 `privacy_level` 與 `tags`
- [ ] CitationBuilder 抽取的 quote 有邊界處理（避免擷取整個 chunk）
- [ ] CitationValidator 同時檢查 hash 與 retrieved context
- [ ] `rdos search` 輸出包含至少 `title`、`heading_path`、`score`、`chunk_id`
