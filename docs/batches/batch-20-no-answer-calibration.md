# Batch 20：No-answer Calibration（v0.2 Trust Runtime 第二批）

## 目標

讓 RDOS 在證據不足時**不硬答**。這是 retrieval quality 最大缺口。

## 背景

Batch 13 加了 no-answer framework，但 `no_answer_threshold` 預設 0（disabled）。原因：

- Fake embedding RRF score ~0.01
- Real bge-m3 RRF score 仍然 ~0.01（RRF 公式限制了 range）
- 沒有 per-collection 校準

v0.2 必須校準、啟用、上 release gate。

## Agent 任務

### 1. Real No-answer Eval Set

新增 `eval_sets/no_answer.jsonl`，至少 30 筆：

| 類型 | 數量 |
| --- | --- |
| 完全虛構（XYZFakePaper2026） | 10 |
| 概念漂移（GraphRAG 在生物學） | 10 |
| 拼寫誤導（AgentTrace 寫成 AgentTrase） | 5 |
| 領域外（clawd-research 沒有的主題） | 5 |

每筆 `answer_type: "no_answer"`。

### 2. Per-collection Score Threshold

`configs/rag.yaml` 新增：

```yaml
retrieval:
  no_answer_thresholds:
    default: 0.005
    clawd-research: 0.008
    sample_data: 0.0
```

校準方式：

- 對每個 collection 跑 real query set
- 取 top score 分布 p5 為 threshold
- 低於 threshold → `no_answer_triggered`

### 3. Insufficient Evidence Answer

`rdos ask` 觸發 no-answer 時，回：

```
目前資料庫沒有足夠證據回答這個問題。

Top score: 0.0034 (threshold: 0.008)
Retrieved chunks: 0 passed threshold
```

**不**回幻覺答案。**不**回 stub fallback 文字。

### 4. Citation Coverage Threshold

Synthesis 必須有最低 citation coverage：

```yaml
retrieval:
  min_citation_coverage: 0.6
```

Coverage < threshold → synthesis 標 `low_confidence` + 提示使用者。

### 5. No-answer Trace Reason

trace 必須記錄：

```json
{
  "no_answer_triggered": true,
  "no_answer_reason": "top_score_below_threshold",
  "top_score": 0.0034,
  "threshold": 0.008,
  "retrieved_chunk_count": 0
}
```

### 6. No-answer Release Gate

新增 release gate metric：

| Metric | Target |
| --- | --- |
| No-answer Accuracy | ≥ 0.90 |
| False No-answer Rate | ≤ 0.05 |

- No-answer Accuracy：no_answer eval set 裡，正確觸發 no-answer 的比例
- False No-answer：real query set 裡，誤觸發 no-answer 的比例

## 需求

1. 新增 `eval_sets/no_answer.jsonl` ≥ 30 筆。
2. `configs/rag.yaml` 支援 per-collection `no_answer_thresholds`。
3. `rdos ask` 觸發 no-answer 時回 insufficient evidence 文字，不硬答。
4. Synthesis 加 `min_citation_coverage` 檢查。
5. trace 記錄 no-answer reason 與分數。
6. release gate 加 No-answer Accuracy ≥ 0.90、False No-answer Rate ≤ 0.05。
7. tests 必須覆蓋：
   - no_answer_threshold 校準邏輯
   - synthesis low_confidence 路徑
   - trace 欄位

## 驗收

```bash
uv run pytest
uv run ruff check .

# 真實 no-answer query
uv run rdos ask "我有沒有整理過完全不存在的 XYZFakePaper2026？" \
  --embedding-provider local-bge-m3
# → insufficient evidence

# Real query 不誤觸發
uv run rdos ask "GraphRAG 是什麼？" --embedding-provider local-bge-m3
# → 正常答案

uv run rdos eval all
# → No-answer Accuracy ≥ 0.90、False No-answer Rate ≤ 0.05
```

## 完成後輸出

1. 修改檔案
2. no_answer threshold 校準結果
3. no-answer eval set 摘要
4. release gate 截圖
5. 驗收結果
6. 下一個建議 batch

## Commit

```
feat(batch-20): calibrate no-answer framework with release gate
```
