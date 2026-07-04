# Batch 3：SQLite Metadata Store + LanceDB Vector Store

## 目標

建立 index pipeline。

## Agent 任務

請實作 RDOS 的 indexing pipeline。

新增檔案：

- `src/rdos/rag/indexer.py`
- `src/rdos/rag/storage_sqlite.py`
- `src/rdos/rag/vector_store.py`
- `src/rdos/cli/index.py`

## 需求

1. `rdos index <path>` 可以掃描資料夾內所有 `.md` 檔案。
2. 使用 `markdown_parser + chunker` 產生 `DocumentChunk`。
3. SQLite 儲存：
   - document metadata（doc_id、file_path、title、date、tags、privacy_level、content_hash）
   - chunk metadata（chunk_id、doc_id、heading_path、chunk_hash、privacy_level、token_count）
4. LanceDB 儲存：
   - chunk embedding
   - chunk metadata（含 chunk_id 對應）
5. embedding 先使用 deterministic fake embedding，避免依賴外部模型。
   - 例如：hash chunk_id → 固定向量
6. `index` 結束後顯示：
   - `Indexed documents: N`
   - `Generated chunks: N`
   - `SQLite updated: data/sqlite/rdos.db`
   - `LanceDB updated: data/lancedb`
7. 重複 index 不應產生重複 chunk（依 `chunk_hash` 去重）。
8. 加入 tests。

## 限制

- 暫時不要接真 embedding
- 不要接 LLM

## 驗收

```bash
uv run rdos index ./sample_data/notes
```

預期輸出：

```
Indexed documents: 5
Generated chunks: <N>
SQLite updated: data/sqlite/rdos.db
LanceDB updated: data/lancedb
```

## Fake Embedding 規格

為了讓後續 batch 可替換，fake embedding 必須滿足：

1. **Deterministic**：同一個 `chunk_id` 永遠產生同一個向量。
2. **固定維度**：建議 384 或 768 維（與後續可能替換的 MiniLM / BGE 一致）。
3. **可替換介面**：定義 `EmbeddingProvider` 抽象，fake 是其中一個實作。

```python
class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

## SQLite Schema 參考

```sql
CREATE TABLE documents (
    doc_id TEXT PRIMARY KEY,
    file_path TEXT,
    title TEXT,
    date TEXT,
    tags TEXT,  -- JSON array
    privacy_level TEXT,
    content_hash TEXT,
    indexed_at TEXT
);

CREATE TABLE chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT,
    heading_path TEXT,  -- JSON array
    chunk_hash TEXT,
    privacy_level TEXT,
    token_count INTEGER,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);
```

## 檢查清單

- [ ] 重複執行 `rdos index` 不會產生 duplicate chunks
- [ ] SQLite 路徑可由 config 覆寫
- [ ] LanceDB 路徑可由 config 覆寫
- [ ] fake embedding 是 deterministic
