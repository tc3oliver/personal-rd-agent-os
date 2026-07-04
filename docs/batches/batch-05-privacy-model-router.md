# Batch 5：Privacy Router + Model Router

## 目標

把 RDOS 的核心差異做出來：privacy-aware model routing。

## Agent 任務

請實作 Privacy Router 與 Model Router。

新增檔案：

- `src/rdos/llm/privacy_router.py`
- `src/rdos/llm/model_router.py`
- `tests/test_privacy_router.py`
- `tests/test_model_router.py`

## 需求

### Privacy Router

1. `PrivacyRouter` 支援以下 privacy order（由低到高）：

   ```
   public < private_summary < private_raw < company_sensitive
   ```

2. 實作 `calculate_effective_privacy`：

   ```python
   effective_privacy_level = max(
       user_query_privacy_level,
       retrieved_chunk_privacy_levels,
       tool_result_privacy_level,
       memory_context_privacy_level,
       trace_context_privacy_level,
   )
   ```

3. 規則：
   - `private_raw` **不可** 使用 external model
   - `company_sensitive` **不可** 使用 external model
   - `private_summary` 使用 cloud model 時，`requires_user_confirmation = true`

### Model Router

4. `ModelRouter` 根據以下三個維度選 model profile：
   - `task_type`
   - `risk_level`
   - `effective_privacy_level`

5. Routing decision 必須回傳 `ModelRoutingDecision` schema（Batch 1 已定義）。

## 測試案例

tests 必須覆蓋以下情境：

| 情境 | 預期 profile | 預期 confirmation |
| --- | --- | --- |
| public synthesis | `cloud_reasoning` | false |
| private_raw research_memory | `local_fast` | false |
| company_sensitive code task | `local_fast` 或 blocked | false |
| private_summary cloud escalation | `cloud_reasoning` | true |

## 限制

- 不要在 `ModelRouter` 裡 `bind_tools`（Batch 6 才會接 LLM）
- 這一批是核心，不要放過

## 驗收

```bash
uv run pytest tests/test_privacy_router.py
uv run pytest tests/test_model_router.py
```

## 介面參考

```python
from rdos.llm.privacy_router import PrivacyRouter, PrivacyInput
from rdos.llm.model_router import ModelRouter, RoutingInput

privacy = PrivacyRouter(...)
decision = privacy.calculate_effective_privacy(PrivacyInput(
    user_query="...",
    retrieved_chunks=[...],
    tool_results=[...],
    memory_context=[...],
    trace_context=[...],
))

router = ModelRouter(...)
routing = router.select(RoutingInput(
    task_type="research_memory",
    risk_level="low",
    effective_privacy_level=decision.effective_privacy_level,
))
```

## Model Profile 對照表（参考）

| Profile | Provider | 適用情境 |
| --- | --- | --- |
| `local_fast` | local llama.cpp | 低成本、低風險、private_raw / company_sensitive |
| `cloud_reasoning` | cloud (e.g. GPT/Claude) | 高推理、public / private_summary |
| `long_context` | cloud long-context | > 32k context |
| `code_specialist` | cloud code model | 程式碼生成、review |

## 檢查清單

- [ ] effective privacy 計算涵蓋所有 5 個 input source
- [ ] private_raw 永遠不選 external model
- [ ] company_sensitive 永遠不選 external model
- [ ] private_summary 升級到 cloud 時 `requires_user_confirmation = true`
- [ ] 4 個測試情境全部通過
