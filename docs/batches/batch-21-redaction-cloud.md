# Batch 21：Redaction + Cloud Escalation（v0.2 Trust Runtime 第三批）

## 目標

讓 `private_summary` 真的可以**安全** escalation 到 cloud model。讓 model routing 從「local only」進化成真正的 privacy-aware hybrid routing。

## 背景

Batch 5 的 PrivacyRouter 已經定義 `private_summary` 可以用 cloud 但需要 confirmation。Batch 19 的 HITL 補上 confirmation 流程。但**沒有 redaction**，所以 escalation 等於把 private 內容整包送雲端。

v0.2 必須補 redaction。

## Agent 任務

### 1. private_raw → private_summary Redaction Pipeline

新增 `src/rdos/llm/redaction.py`：

- Input：private_raw chunk text
- Output：private_summary chunk text（PII / company scrubbed）
- 用 rule-based + recognizer 雙層

### 2. PII / Company Name Scrubber

Recognizers：

| 類型 | 抓什麼 |
| --- | --- |
| EMAIL | `[\w.+-]+@[\w.-]+\.\w+` |
| PHONE_TW | `09\d{8}`、`\+886\d{9,10}` |
| ID_TW | 身分證字號 `[A-Z]\d{9}` |
| URL | `https?://...` |
| COMPANY_HINT | 從 `configs/redaction.yaml` 載入公司名、產品名 |
| IP | IPv4 / IPv6 |
| CREDIT_CARD | 16 digit Luhn |
| ADDRESS_TW | 縣市/路段/號 regex |

每個 recognizer 輸出 `(start, end, type, replacement)`。

### 3. Redaction Config

`configs/redaction.yaml`：

```yaml
enabled_recognizers:
  - EMAIL
  - PHONE_TW
  - ID_TW
  - URL
  - COMPANY_HINT
  - IP
  - CREDIT_CARD
  - ADDRESS_TW

company_names:
  - 公司A
  - 產品X
  - 內部代號 Y

replacement_strategy: placeholder   # placeholder | mask | hash
placeholder_format: "[REDACTED-{TYPE}]"
```

### 4. Redaction Evaluator

`rdos eval redaction`：

- 對 30 條含已知 PII 的 sample 跑 redaction
- Metric：recall（該抓的都抓到）、precision（沒誤抓）、coverage

Release gate 加：

| Metric | Target |
| --- | --- |
| Redaction Recall | ≥ 0.95 |
| Redaction Precision | ≥ 0.95 |

### 5. Cloud Escalation Approval Flow

`private_summary` query → cloud escalation 時：

1. 先 redact 檢索到的 chunks
2. 送 redacted 版本到 cloud
3. trace 記錄 redacted 內容 + cloud response
4. Approval queue 觸發（Batch 19 機制）

### 6. Prompt Privacy Validator

`src/rdos/llm/prompt_privacy_validator.py`：

- 對即將送 cloud 的 prompt 跑最後一次掃描
- 若發現未被 redact 的 PII → block + 警告
- 是 last-line-of-defense

### 7. Trace Redaction

trace 寫入前先 redact：

- `user_query`
- `retrieved_chunks` 內容
- `final_answer`
- `raw_answer`

避免 trace 檔案本身變成 side channel。

## 需求

1. 實作 `src/rdos/llm/redaction.py` 與 8 個 recognizer。
2. `configs/redaction.yaml` 控制 recognizer 開關與公司名。
3. `private_summary` cloud escalation 必須先 redact。
4. Prompt privacy validator 為最後防線，發現殘留 PII 必報錯。
5. trace 寫入前 redact。
6. `rdos eval redaction` 納入 release gate。
7. tests 必須覆蓋：
   - 每個 recognizer 抓到正確範圍
   - redact 後再 cloud escalation 不含原始 PII
   - prompt privacy validator block 路徑

## 驗收

```bash
uv run pytest
uv run ruff check .
uv run rdos eval redaction
uv run rdos eval all

# 示範：private_summary cloud escalation（redact 後）
uv run rdos ask "整理我關於 X 的策略筆記" \
  --embedding-provider local-bge-m3 \
  --llm-mode cloud
# → 觸發 redaction → approval → cloud → trace 顯示 redacted 版本
```

## 完成後輸出

1. 修改檔案
2. recognizer 列表與 recall/precision
3. redaction pipeline 流程圖
4. release gate 截圖（含 Redaction Recall）
5. 驗收結果
6. 下一個建議 batch

## Commit

```
feat(batch-21): redaction pipeline with cloud escalation approval
```
