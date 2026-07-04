# Batch 6：Local LLM Adapter + Structured Formatter

## 目標

接上本地 llama.cpp，但不要把它綁死在主流程。

## Agent 任務

請實作 local llama.cpp adapter 與 structured output formatter。

新增檔案：

- `src/rdos/llm/local_llama_cpp.py`
- `src/rdos/llm/structured_output.py`
- `scripts/check_local_llm.sh`
- `scripts/check_langchain_llama_cpp.py`

## 需求

### Local LLM Adapter

1. 支援 OpenAI-compatible chat completion（llama.cpp 的 server 模式）。
2. 從 `configs/models.yaml` 讀取 `base_url` 與 `model`。
3. 提供：

   ```python
   generate_text(
       messages: list[Message],
       model_profile: str,
   ) -> str
   ```

### Structured Output Formatter

4. 提供：

   ```python
   format_structured_output(
       text: str,
       schema: type[BaseModel],
   ) -> StructuredResult
   ```

5. formatter 使用 Pydantic validation。
6. validation fail 時 retry once（可重新提示模型產出 JSON）。
7. 如果還是失敗，回傳 structured error（不 raise）。

### Compatibility Test Scripts

8. 寫 compatibility test script，測試以下項目：
   - basic invoke
   - streaming
   - JSON output
   - `response_format`
   - tool calling（如果支援）
   - `enable_thinking`（如果支援）

## 限制

- **不要在 `ModelRouter` 裡 `bind_tools`**
- adapter 必須可替換（之後可換成 `cloud_provider`）
- formatter 與 LLM 解耦

## 驗收

```bash
bash scripts/check_local_llm.sh
uv run python scripts/check_langchain_llama_cpp.py
```

## Adapter 介面參考

```python
class LLMAdapter(Protocol):
    def generate(
        self,
        messages: list[Message],
        model_profile: str,
        **kwargs,
    ) -> LLMResponse: ...

class LocalLlamaCppAdapter(LLMAdapter):
    def __init__(self, base_url: str, model: str): ...
```

## Structured Output 介面參考

```python
class StructuredResult(BaseModel):
    success: bool
    data: BaseModel | None
    error: StructuredError | None
    retries: int

class StructuredError(BaseModel):
    code: str         # e.g. "json_parse_error", "validation_error"
    message: str
    raw_output: str
```

## check_local_llm.sh 範例結構

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${LOCAL_LLM_BASE_URL:-http://localhost:8080}"
MODEL="${LOCAL_LLM_MODEL:-qwythos-9b-q4}"

echo "Checking local llama.cpp at $BASE_URL"
curl -s "$BASE_URL/v1/models" | jq '.data[0].id'

echo "Running langchain compatibility checks..."
uv run python scripts/check_langchain_llama_cpp.py
```

## 檢查清單

- [ ] `base_url` 與 `model` 完全由 config 驅動
- [ ] adapter 不直接綁死 LangChain（可用 langchain-openai 作為底層）
- [ ] formatter 第一次失敗會 retry once
- [ ] retry 失敗回傳 `StructuredResult(success=False, ...)`，不 raise
- [ ] compatibility script 至少測 basic invoke、streaming、JSON output
- [ ] `bind_tools` 不出現在 ModelRouter
