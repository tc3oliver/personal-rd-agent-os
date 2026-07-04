# Batch 17：Hardening, Adversarial Eval, Portfolio Release

## 目標

最後一批做硬化與公開展示。不再新增大功能，而是把專案變成可以放履歷、GitHub、面試講的版本。

## Agent 任務

### 1. Adversarial Eval

擴充 eval sets：

| Eval Set | 數量 |
| --- | --- |
| `privacy_routing` | ≥ 50 |
| `model_routing` | ≥ 50 |
| `citation` | ≥ 40 |
| `real_rag_qa` | ≥ 80 |

必含 adversarial cases：

- prompt injection（要求忽略 privacy policy）
- public query 檢到 `private_raw` chunk
- public query 檢到 `company_sensitive` chunk
- `private_summary` cloud escalation requires confirmation
- `private_raw` external block
- `company_sensitive` external block
- hallucinated `chunk_id`
- stale `chunk_hash`
- citation not in retrieved context
- unsupported claim
- no-answer cases
- embedding provider mismatch
- tool path traversal
- blocked secrets read

### 2. Benchmark Report

```bash
rdos benchmark all
```

輸出 `data/reports/benchmark_report.md`，包含：

- embedding provider metadata
- retrieval metrics（Recall@3 / Recall@5 / MRR / hit rates）
- ask latency p50 / p95
- citation validity
- privacy compliance
- tool permission results
- local model health
- failure cases

### 3. Demo Scripts

新增：

- `scripts/demo_foundation.sh`
- `scripts/demo_real_corpus.sh`
- `scripts/demo_eval.sh`
- `scripts/demo_trace.sh`

### 4. README 重寫成 Portfolio 版

首屏：

> This is not a chatbot.
> This is a local-first, model-agnostic, privacy-aware R&D agent runtime.

必含 section：

- core loop
- architecture diagram
- CLI demo
- trace example
- eval report
- privacy model
- model routing
- what is real vs stub
- limitations
- roadmap

### 5. Docs 補強

- `docs/release_notes/v0.1.0-foundation.md`
- `docs/limitations.md`
- `docs/demo_script.md`

### 6. Release Tag

通過後：

```bash
git tag v0.1.0-foundation
```

## 需求

1. 擴充 eval sets（見上表數量）。
2. adversarial cases 必須涵蓋上列 14 種情境。
3. 新增 `rdos benchmark all`。
4. benchmark report 輸出到 `data/reports/benchmark_report.md`。
5. benchmark report 包含：embedding provider metadata / retrieval metrics / ask latency / citation validation / privacy compliance / tool permission results / local model health / failed cases。
6. 新增 4 個 demo scripts（見上）。
7. README 重寫成 portfolio-ready（見上 section 清單）。
8. docs 補 release notes / limitations / demo script。
9. **不要把 private real notes commit 進 repo**。
10. `data/` runtime outputs 不可進 git；samples 可以 redacted。
11. release gate 不可降低。
12. 所有 tests / ruff / eval / benchmark 必須通過。

## 驗收

```bash
uv run pytest
uv run ruff check .
uv run rdos eval all
uv run rdos benchmark all
bash scripts/demo_foundation.sh
bash scripts/demo_eval.sh
git status --short
```

## 完成後輸出

1. 修改檔案
2. adversarial eval summary
3. benchmark summary
4. README 更新摘要
5. release readiness checklist
6. 建議 git tag

## Commit

```
chore(batch-17): harden eval benchmark and portfolio release
```

## Tag

```
git tag v0.1.0-foundation
```

## 後續（不在本批範圍）

`v0.1.0-foundation` 是 portfolio release。後續可能的方向：

- v0.2：HITL approval UI（接 Batch 15 的 `approval_required`）
- v0.3：multi-turn conversation
- v0.4：cloud escalation + redaction pipeline
- v0.5：plugin 外部資料源（GitHub issues、arXiv）
