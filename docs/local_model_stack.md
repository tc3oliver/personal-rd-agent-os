# Local Model Stack

RDOS 開發環境可用的本地模型端點。本機参考使用，正式 config 以 `configs/models.yaml` 與 `.env` 為準。

## 端點總覽

| 服務 | URL | Model | 用途 |
| --- | --- | --- | --- |
| Chat (reasoning) | `http://10.10.10.12:8080` | `qwythos-9b-q4` | Batch 6 Local LLM Adapter |
| Embedding | `http://10.10.10.12:8081` | `bge-m3-q8_0` | Batch 3 向量 index（取代 fake embedding） |

- Auth header：`Authorization: Bearer local-dev-key`
- 兩個服務皆為 OpenAI-compatible API。

## 1. Health Check

先確認兩個服務都通：

```bash
curl http://10.10.10.12:8080/health
curl http://10.10.10.12:8081/health
```

## 2. Chat（8080）

### 基本問答

```bash
curl http://10.10.10.12:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-key" \
  -d '{
    "model": "qwythos-9b-q4",
    "messages": [{"role": "user", "content": "用一句繁中介紹你自己"}],
    "max_tokens": 1000
  }'
```

### Streaming

```bash
curl -N http://10.10.10.12:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-key" \
  -d '{
    "model": "qwythos-9b-q4",
    "stream": true,
    "messages": [{"role": "user", "content": "hi"}]
  }'
```

> ⚠️ **reasoning 模型，`max_tokens` 要給夠**：純問答 ≥ 1000；若要關閉思考鏈，加上：
> `"chat_template_kwargs": {"enable_thinking": false}`

## 3. Embedding（8081）

模型為 `bge-m3-q8_0`，**輸出 1024 維向量**。

### 單筆

```bash
curl http://10.10.10.12:8081/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-key" \
  -d '{
    "model": "bge-m3-q8_0",
    "input": "hello world"
  }'
```

### Batch（多筆一次，效率高）

```bash
curl http://10.10.10.12:8081/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-key" \
  -d '{
    "model": "bge-m3-q8_0",
    "input": ["貓很可愛", "貓咪很萌", "量子力學方程式"]
  }'
```

## 與 RDOS Batch 的對應

| Batch | 用途 | 對應端點 |
| --- | --- | --- |
| Batch 3 | RAG index 的 chunk embedding | 8081（取代 fake embedding） |
| Batch 4 | Query embedding（semantic search） | 8081 |
| Batch 6 | `local_fast` profile 的 LLM | 8080 |
| Batch 7 | `generate_answer` node | 8080 |

## 整合注意事項

1. **Embedding 維度**：本環境為 **1024 維**，LanceDB schema 需對齊。
   - Batch 3 的 fake embedding 需改成 1024 維，或保留可抽換介面。
2. **Reasoning token**：Batch 6 的 `generate_text` 預設 `max_tokens` 應 ≥ 1000。
3. **Batch embedding**：Batch 3 index 時應使用 batch input，避免逐筆呼叫。
4. **Privacy**：這兩個端點視為 **local provider**，`private_raw` 與 `company_sensitive` 可使用。
5. **失敗 fallback**：若 8080 / 8081 不可達，Batch 6 應透過 `LLMAdapter` 抽象退回 fake/dry-run，不應導致 workflow 崩潰。

## `.env.example` 對應欄位

```bash
LOCAL_LLM_BASE_URL=http://10.10.10.12:8080
LOCAL_LLM_MODEL=qwythos-9b-q4
LOCAL_LLM_API_KEY=local-dev-key

LOCAL_EMBED_BASE_URL=http://10.10.10.12:8081
LOCAL_EMBED_MODEL=bge-m3-q8_0
LOCAL_EMBED_API_KEY=local-dev-key
LOCAL_EMBED_DIM=1024
```
