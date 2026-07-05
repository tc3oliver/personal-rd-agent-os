# Batch 11：Real Local Model Runtime Integration

## 目標

把 RDOS 從 fake/stub runtime 升級成真實本地模型 runtime。核心閉環已通，但 embedding 還用 `FakeEmbeddingProvider`、LLM 主要 fallback 到 `StubLLMAdapter`。這批一次把 fake 換成真實本地模型，並補上 mode control、health check、provider metadata、防呆。

## Agent 任務

可用本地模型服務：

**Chat**
- base_url: `http://localhost:8080/v1`
- model: `qwythos-9b-q4`
- auth: `Bearer local-dev-key`
- OpenAI-compatible chat completions
- reasoning 模型，純問答 `max_tokens` 建議 ≥1000
- 可用 `chat_template_kwargs.enable_thinking=false` 關思考鏈

**Embedding**
- base_url: `http://localhost:8081/v1`
- model: `bge-m3-q8_0`
- auth: `Bearer local-dev-key`
- OpenAI-compatible embeddings
- output dimension: **1024**
- 支援 batch input

## 需求

1. 保留 `FakeEmbeddingProvider` 作為 tests / CI provider。
2. 新增 `OpenAICompatibleEmbeddingProvider`，用於 `bge-m3-q8_0`。
3. `configs/models.yaml` 或 `configs/rag.yaml` 可設定 embedding `provider` / `base_url` / `model` / `dim` / `timeout` / `api_key` env var。
4. `.env.example` 補上：
   ```bash
   RDOS_LOCAL_CHAT_BASE_URL
   RDOS_LOCAL_CHAT_MODEL
   RDOS_LOCAL_EMBEDDING_BASE_URL
   RDOS_LOCAL_EMBEDDING_MODEL
   RDOS_LOCAL_MODEL_API_KEY
   ```
5. `rdos index` 支援 `--embedding-provider fake|local-bge-m3`。
6. `rdos search` 支援 `--embedding-provider fake|local-bge-m3`。
7. LanceDB table metadata 必須保存 `embedding_provider` / `embedding_model` / `embedding_dim`。
8. provider 或 dim mismatch 時必須明確報錯，**不可 silent mismatch**。
9. `rdos ask` 新增 `--llm-mode stub|local|auto`。
10. `local` mode 必須使用 `LocalLlamaCppAdapter`，連線失敗 **不可 fallback**。
11. `auto` mode 可 fallback stub，但 CLI 與 trace 都要顯示 fallback warning。
12. trace 必須記錯 `requested_llm_mode` / `actual_llm_adapter` / `fallback_used` / `fallback_reason` / embedding provider metadata。
13. 新增 `scripts/check_local_model_stack.py` 或 `rdos doctor models`。
14. tests 不依賴外部服務，仍使用 fake/stub。
15. README 補上 local model stack 使用方式。
16. `docs/local_model_stack.md` 保留作為環境參考，但正式設定以 configs + `.env` 為準。

## Embedding Provider 架構

```
EmbeddingProvider (Protocol)
├── FakeEmbeddingProvider          (deterministic hash, tests/CI)
└── OpenAICompatibleEmbeddingProvider
    └── 用於 bge-m3-q8_0 (dim=1024)
```

`build_embedding_provider(name)` 工廠依 config / CLI flag 分派。

## LLM Mode 行為

| mode | 行為 |
| --- | --- |
| `stub` | 永遠使用 `StubLLMAdapter` |
| `local` | 必須使用 qwythos，失敗就報錯（**不 fallback**） |
| `auto` | 優先 local，失敗 fallback stub，但要明確 warning（CLI + trace） |

## Provider / Dimension 防呆

LanceDB table metadata：

```json
{
  "embedding_provider": "local-bge-m3",
  "embedding_model": "bge-m3-q8_0",
  "embedding_dim": 1024
}
```

Search 時：
- 若 query embedding dim ≠ table dim → raise `EmbeddingDimensionMismatch`
- 若 query provider ≠ table provider → raise `EmbeddingProviderMismatch`，提示 reindex

## 驗收

```bash
uv run pytest
uv run ruff check .
uv run python scripts/check_local_model_stack.py
uv run rdos index ./sample_data/notes --embedding-provider local-bge-m3
uv run rdos search "hybrid retrieval metadata filtering" --embedding-provider local-bge-m3
uv run rdos ask "RAG filtering 是什麼？" --llm-mode local --embedding-provider local-bge-m3
uv run rdos trace show <run_id>
```

## 完成後輸出

1. 修改檔案
2. embedding provider 架構
3. LLM mode 行為
4. provider/dim mismatch 防呆方式
5. 驗收結果
6. 下一個建議 batch

## Commit

```
feat(batch-11): integrate real local embedding and llm runtime
```
