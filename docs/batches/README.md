# RDOS Implementation Batches

本資料夾把 RDOS（Personal R&D Agent OS）的實作拆成多個 batch，每個 batch 都是可獨立驗收、可交付給 agent 執行的工作單元。

## Phase 1 — Foundation（Batch 0–10，已完成）

核心閉環：Markdown → index → retrieve → cite → privacy route → model route → generate → structure → validate → trace → eval。

| Batch | 主題 | 核心目標 | 狀態 |
| --- | --- | --- | --- |
| [Batch 0](./batch-00-skeleton.md) | 專案骨架 | uv + pyproject + rdos CLI + 目錄 + Fake provider | ✅ |
| [Batch 1](./batch-01-schema-config.md) | Schema + Config | Pydantic schemas + YAML loader | ✅ |
| [Batch 2](./batch-02-parser-chunker.md) | Markdown Parser + Chunker | heading-aware + chunk_hash dedup | ✅ |
| [Batch 3](./batch-03-index-pipeline.md) | SQLite + LanceDB Index | idempotent index pipeline | ✅ |
| [Batch 4](./batch-04-retriever-citation.md) | Hybrid Retriever + Citation | RRF + 三重 citation 驗證 | ✅ |
| [Batch 5](./batch-05-privacy-model-router.md) | Privacy + Model Router | effective privacy、不綁 tools | ✅ |
| [Batch 6](./batch-06-local-llm-formatter.md) | Local LLM + Structured Output | llama.cpp adapter + retry once | ✅ |
| [Batch 7](./batch-07-research-graph-ask.md) | Research Graph + Ask CLI | 11-node workflow + rdos ask | ✅ |
| [Batch 8](./batch-08-trace-store.md) | Trace Store | JSONL self-contained record | ✅ |
| [Batch 9](./batch-09-eval-harness.md) | Eval Harness + Release Gate | 8 metrics，gate PASS | ✅ |
| [Batch 10](./batch-10-portfolio-polish.md) | Portfolio Polish | README / case studies / samples | ✅ |

## Phase 2 — Production Realism（Batch 11–17）

把 RDOS 從「可驗證的 foundation workflow」推進成「真的吃 2000+ 篇研究筆記、真的用 bge-m3、真的用 qwythos、真的可追蹤可評估的個人研究助理」。

| Batch | 主題 | 核心目標 | 驗收重點 |
| --- | --- | --- | --- |
| [Batch 11](./batch-11-real-local-runtime.md) | Real Local Model Runtime | bge-m3 + qwythos + mode control + provider metadata | provider/dim mismatch 防呆 |
| [Batch 12](./batch-12-real-corpus-ingestion.md) | Real Research Corpus Ingestion | 接入 clawd-research + 增量 index + index report | `rdos index-corpus clawd-research --scope rag/agent/eval` |
| [Batch 13](./batch-13-retrieval-quality.md) | Retrieval Quality Hardening | real benchmark + query rewrite + no-answer | Recall@5、GraphRAG/AgentTrace/Argus query 搜得準 |
| [Batch 14](./batch-14-langgraph-runtime.md) | LangGraph Runtime + Checkpoint | StateGraph + thread_id + node-level trace | `graph_runtime=langgraph` in trace |
| [Batch 15](./batch-15-tool-permission.md) | Runtime Tool Permission | PermissionGate + CapabilityBoundary + safe tools | `.env` / traversal / symlink escape 必被拒 |
| [Batch 16](./batch-16-research-apps.md) | Real Research Apps | digest / topic / synthesize | synthesize 每個 claim 都 cite |
| [Batch 17](./batch-17-hardening-release.md) | Hardening + Portfolio Release | adversarial eval + benchmark + tag | `git tag v0.1.0-foundation` |

## 執行順序

```
Phase 1（已完成）
  Batch 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → {8, 9} → 10

Phase 2（依賴 Phase 1 完成）
  Batch 11 (real runtime)
    └─ Batch 12 (real corpus)
         └─ Batch 13 (retrieval quality)
              └─ Batch 14 (langgraph)
                   ├─ Batch 15 (tool permission)
                   └─ Batch 16 (research apps)
                        └─ Batch 17 (release)
```

Batch 11 是 Phase 2 的入口：沒有 real runtime，後續 batch 都只能跑 fake/stub。
Batch 17 同時是 release gate，必須在 11–16 全部完成後才能 tag。

## Release Gate（Batch 9 定義，Batch 17 擴充）

| Metric | Target | 定義處 | 擴充處 |
| --- | --- | --- | --- |
| RAG Recall@5 | ≥ 0.75 | Batch 9 | Batch 13 加 real_rag_qa |
| Citation Accuracy | ≥ 0.70 | Batch 9 | Batch 17 adversarial |
| Valid Chunk Reference Rate | ≥ 0.95 | Batch 9 | — |
| Structured Output JSON Validity | ≥ 0.95 | Batch 9 | — |
| Model Routing Correct Rate | ≥ 0.85 | Batch 9 | Batch 17 adversarial |
| Privacy Policy Compliance | = 1.00 | Batch 9 | Batch 17 adversarial |
| Private Raw Leakage Rate | = 0 | Batch 9 | Batch 17 adversarial |
| Company-sensitive Leakage Rate | = 0 | Batch 9 | Batch 17 adversarial |

任一指標未達標即不可 release。Batch 17 後 release gate 不可降低。

## 設計原則

每個 batch 皆遵循：

1. **單一職責**：一批只做一件事，避免橫向耦合。
2. **可驗收**：每批都有明確的 CLI 或 pytest 驗收指令。
3. **可交付給 agent**：以「Agent 任務」描述，直接餵給 executor agent 即可執行。
4. **不過早實作**：明確標註「不要接 LLM」「不要接真 embedding」等限制。
5. **架構可替換**：fake embedding、stub LLM 皆預留替換點。
6. **Phase 2 不破壞 Phase 1**：fake/stub 永遠保留作為 CI / offline 路徑。

## 建議 commit 順序

```
feat(batch-11): integrate real local embedding and llm runtime
feat(batch-12): ingest real clawd research corpus
feat(batch-13): harden retrieval quality on real research corpus
feat(batch-14): migrate research workflow to langgraph runtime
feat(batch-15): enforce runtime tool permission gate
feat(batch-16): add real research digest topic and synthesis apps
chore(batch-17): harden eval benchmark and portfolio release
```

## 相關文件

- [Local Model Stack](../local_model_stack.md) — 開發環境可用的本地 LLM / Embedding 端點（影響 Batch 3, 4, 6, 7, 11）
- [Architecture Spec](../architecture.md) — 完整 v1 架構設計
- [Architecture Overview](../architecture_overview.md) — 高階架構圖與 component map
- [Case Studies](../case_studies/README.md) — model routing / privacy / citation / resume positioning

