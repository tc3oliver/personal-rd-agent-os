# RDOS Implementation Batches

本資料夾把 RDOS（Personal R&D Agent OS）的實作拆成 10 個 batch，每個 batch 都是可獨立驗收、可交付給 agent 執行的工作單元。

## 總覽

| Batch | 主題 | 核心目標 | 驗收指令 |
| --- | --- | --- | --- |
| [Batch 0](./batch-00-skeleton.md) | 專案骨架 | 可開發、可測試、可擴充的 repo skeleton | `uv run pytest` / `ruff check .` / `rdos --help` |
| [Batch 1](./batch-01-schema-config.md) | Schema + Config Loader | 固定資料契約 | `uv run pytest tests/` |
| [Batch 2](./batch-02-parser-chunker.md) | Markdown Parser + Chunker | 把筆記切成可 index 的 chunks | `pytest test_markdown_parser test_chunker` |
| [Batch 3](./batch-03-index-pipeline.md) | SQLite + LanceDB Index | 可重複執行的 index pipeline | `rdos index ./sample_data/notes` |
| [Batch 4](./batch-04-retriever-citation.md) | Hybrid Retriever + Citation | 查回資料並產生 citation | `rdos search "query"` |
| [Batch 5](./batch-05-privacy-model-router.md) | Privacy Router + Model Router | RDOS 的核心差異 | `pytest test_privacy_router test_model_router` |
| [Batch 6](./batch-06-local-llm-formatter.md) | Local LLM Adapter + Formatter | 接上 llama.cpp，但不綁死 | `bash scripts/check_local_llm.sh` |
| [Batch 7](./batch-07-research-graph-ask.md) | Research Memory Graph + Ask CLI | 第一條完整 agent workflow | `rdos ask "..."` |
| [Batch 8](./batch-08-trace-store.md) | Trace Store | 每次執行都可追蹤 | `rdos trace list` / `trace show` |
| [Batch 9](./batch-09-eval-harness.md) | Eval Harness + Release Gate | 評估驅動、設 release gate | `rdos eval all` |

## 設計原則

每個 batch 皆遵循以下原則：

1. **單一職責**：一批只做一件事，避免橫向耦合。
2. **可驗收**：每批都有明確的 CLI 或 pytest 驗收指令。
3. **可交付給 agent**：以「Agent 任務」描述，直接餵給 executor agent 即可執行。
4. **不過早實作**：明確標註「不要接 LLM」「不要接真 embedding」等限制。
5. **架構可替換**：fake embedding、fake LLM 皆預留替換點。

## 執行順序

Batch 0~9 具有線性依賴：

```
Batch 0 (skeleton)
  └─ Batch 1 (schema + config)
       └─ Batch 2 (parser + chunker)
            └─ Batch 3 (index pipeline)
                 └─ Batch 4 (retriever + citation)
                      └─ Batch 5 (privacy + model router)
                           └─ Batch 6 (local LLM)
                                └─ Batch 7 (research graph + ask)
                                     ├─ Batch 8 (trace)
                                     └─ Batch 9 (eval)
```

Batch 8 與 Batch 9 可平行，但建議先完成 Batch 8（trace）再做 Batch 9（eval），eval 報告會用到 trace 資料。

## Release Gate（Batch 9 定義）

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

任一指標未達標即不可 release。

## 相關文件

- [Local Model Stack](../local_model_stack.md) — 開發環境可用的本地 LLM / Embedding 端點（影響 Batch 3, 4, 6, 7）
- [Architecture Spec](../architecture.md) — 完整 v1 架構設計
