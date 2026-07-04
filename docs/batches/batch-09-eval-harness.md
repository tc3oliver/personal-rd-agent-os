# Batch 9：Eval Harness + Release Gate

## 目標

把 demo 變成 evaluation-driven project。

## Agent 任務

請實作 evaluation harness。

新增檔案：

### Eval Sets

- `eval_sets/rag_qa.jsonl`
- `eval_sets/citation.jsonl`
- `eval_sets/model_routing.jsonl`
- `eval_sets/privacy_routing.jsonl`

### Eval Modules

- `src/rdos/eval/rag_eval.py`
- `src/rdos/eval/citation_eval.py`
- `src/rdos/eval/model_routing_eval.py`
- `src/rdos/eval/privacy_eval.py`
- `src/rdos/eval/report.py`
- `src/rdos/cli/eval.py`

## 需求

### CLI

支援以下 5 個子指令：

```
rdos eval rag
rdos eval citation
rdos eval model-routing
rdos eval privacy
rdos eval all
```

### Release Gate

| Metric | Target |
| --- | --- |
| RAG Recall@5 | ≥ 0.75 |
| Citation Accuracy | ≥ 0.70 |
| Valid Chunk Reference Rate | ≥ 0.95 |
| Structured Output JSON Validity | ≥ 0.95 |
| Model Routing Correct Rate | ≥ 0.85 |
| Privacy Policy Compliance | = 1.00 |
| Private Raw Leakage Rate | = 0 |
| Company-sensitive Leakage Rate | = 0 |

### Eval Report

eval report 輸出到 `data/reports/eval_report.md`，內容包含：

1. 各 metric 實際數值
2. pass / fail 標記
3. 失敗 sample 的 query 與預期 / 實際
4. 整體 release gate verdict（`PASS` / `FAIL`）

## Eval Set 格式

### `rag_qa.jsonl`

```json
{"query": "RAG filtering 是什麼？", "expected_doc_ids": ["doc_001"], "expected_keywords": ["metadata filter", "semantic filter"]}
```

### `citation.jsonl`

```json
{"query": "...", "expected_chunk_ids": ["chunk_abc"], "must_cite_at_least": 1}
```

### `model_routing.jsonl`

```json
{"task_type": "research_memory", "privacy_level": "private_raw", "expected_profile": "local_fast"}
```

### `privacy_routing.jsonl`

```json
{"query_privacy": "private_raw", "retrieved_privacy": ["public"], "expected_effective": "private_raw", "must_local": true}
```

## 驗收

```bash
uv run rdos eval all
```

預期輸出（terminal）：

```
RAG Recall@5:                       0.82  PASS (>= 0.75)
Citation Accuracy:                  0.74  PASS (>= 0.70)
Valid Chunk Reference Rate:         0.97  PASS (>= 0.95)
Structured Output JSON Validity:    0.98  PASS (>= 0.95)
Model Routing Correct Rate:         0.90  PASS (>= 0.85)
Privacy Policy Compliance:          1.00  PASS (= 1.00)
Private Raw Leakage Rate:           0.00  PASS (= 0)
Company-sensitive Leakage Rate:     0.00  PASS (= 0)

Release Gate: PASS
Report written to data/reports/eval_report.md
```

## 檢查清單

- [ ] 4 個 eval sets 至少各有 10 條 sample
- [ ] 5 個 eval 子指令都能單獨執行
- [ ] release gate 任一指標未達標即 `FAIL`
- [ ] report 有失敗 sample 的 query 與預期 / 實際
- [ ] leakage metrics 為 0 才算 PASS（hard requirement）
- [ ] eval report 路徑可由 config 覆寫
