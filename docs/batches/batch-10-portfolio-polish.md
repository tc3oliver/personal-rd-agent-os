# Batch 10：Portfolio Polish（已完成）

> **狀態**：✅ 已實作，commit `81b46e3`
> 這份文件是事後補的回顧；Phase 1 沒有 pre-implementation 計畫文件。

## 目標

把 repo 從「可運作的 foundation」推進成「可公開的 portfolio 作品」。

## 完成內容

### 文件

- `README.md` 重寫，含 core loop、CLI demo、design constraints、status
- `docs/architecture_overview.md` — high-level 架構圖 + component map
- `docs/case_studies/README.md` — case study 索引
- `docs/case_studies/model_routing.md` — 為何 router 不綁 tools
- `docs/case_studies/privacy_routing.md` — effective = max 的理由
- `docs/case_studies/citation_validation.md` — 三重驗證的理由
- `docs/case_studies/resume_positioning.md` — interview 談話腳本
- `data/samples/eval_report.md` — eval report 樣本
- `data/samples/trace_sample.jsonl` — trace 樣本

### 安全性

- 所有 sample notes 都是 synthetic
- 沒有真實個人/公司資料
- `data/` runtime 資料夾用 `.gitkeep` 保留結構，內容 gitignore

## 驗收（回顧）

- ✅ `uv run pytest`（82 passed at commit time）
- ✅ `uv run ruff check .`
- ✅ `uv run rdos --help`
- ✅ `uv run rdos index ./sample_data/notes`
- ✅ `uv run rdos ask "..."`
- ✅ `uv run rdos eval all`

## Commit

```
docs(batch-10): portfolio polish — README, architecture, case studies
```

## 給 Phase 2 的話

Phase 2（Batch 11–17）會把 `data/samples/` 的 redacted 範例換成 real corpus 的真實 output 範例。Batch 17 的 portfolio release 會回頭檢查這些 sample 是否需要更新或 redact。
