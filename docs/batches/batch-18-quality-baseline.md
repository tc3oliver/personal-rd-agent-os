# Batch 18：Quality Baseline & Release Cleanup

> **狀態**：v0.1.0-foundation 後的第一個文件批次
> **性質**：純文件，不動 runtime code、不降 release gate、不加新測試依賴

## 目標

把 RDOS 從「可運作的 foundation」推進成「可信的公開 release」。不新增 runtime、不新增 app、不誇大 production-grade。

## Agent 任務

### 1. 更新 `README.md`

新增三個 section：

#### What is real in v0.1.0

明確列：

- real local embedding: bge-m3-q8_0
- real local LLM: qwythos-9b-q4
- real clawd-research ingestion（2,088 files，已測 476）
- LangGraph StateGraph runtime
- runtime tool permission gate
- citation validation（三重檢查）
- JSONL trace
- digest / topic / synthesis research apps
- adversarial eval sets

#### Quality Baseline

明確拆兩個 gate：

| Gate | 用什麼資料 | 用途 |
| --- | --- | --- |
| Foundation regression gate | `sample_data/notes` + `fake` provider | 每次跑都 deterministic PASS |
| Real corpus benchmark | `clawd-research` + `local-bge-m3` | 真實品質參考（recall@5=0.73） |

#### Known Limitations（要在 README 就講清楚）

- no-answer framework 存在，但 v0.1 預設 disabled
- HITL approval UI / LangGraph interrupt-resume 未實作
- cloud escalation + redaction 未實作
- multi-turn research thread 未實作
- 只 benchmark 過 rag/agent/eval 三個 scope，**不是整個 2,088-file corpus**
- v0.1.0 不是 production-grade agent OS，是 foundation release

### 2. 更新 `docs/release_notes/v0.1.0-foundation.md`

- 移除任何 "production-ready" 字眼
- 明確標「foundation release」
- 引用 `docs/quality_baseline_v0.1.0.md` 而非自吹數字

### 3. 更新 `docs/limitations.md`

必須三層分類：

- **implemented**（v0.1 真的做完）
- **partially implemented**（架構在、運作部分缺）
- **planned**（v0.2+ roadmap）

### 4. 新增 `docs/quality_baseline_v0.1.0.md`

必含 9 個 section：

1. Release identity（tag、commit、日期）
2. What was tested
3. Foundation regression gate results
4. Real corpus benchmark results
5. Retrieval observations
6. Citation validation status
7. Tool permission status
8. Known limitations
9. Recommended next work

## 限制

- ❌ 不要修改 runtime code
- ❌ 不要降低 release gate
- ❌ 不要新增測試依賴

## 驗收

```bash
uv run pytest
uv run ruff check .
git diff -- README.md docs/release_notes/v0.1.0-foundation.md \
              docs/quality_baseline_v0.1.0.md docs/limitations.md
```

## 完成後輸出

1. 修改檔案清單
2. 新增的品質基線內容
3. 修正了哪些過度宣稱
4. final positioning
5. 建議 commit message

## Commit

```
docs(batch-18): clarify v0.1 foundation quality baseline
```

## v0.2 起手式（Batch 18 完成後）

```bash
git checkout -b feat/v0.2-trust-runtime
```

接著 v0.2 文件先寫，再實作（見 [batch-19-hitl-runtime.md] 起）。
