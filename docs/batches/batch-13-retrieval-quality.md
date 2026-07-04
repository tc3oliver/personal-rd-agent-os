# Batch 13：Retrieval Quality Hardening

## 目標

資料進來後，把 retrieval 從「能搜到」提升成「可評估、可調參、可比較」。建立 real corpus retrieval benchmark、query rewrite、hybrid search tuning、no-answer handling。

## Agent 任務

### 1. Retrieval Eval Set from Real Corpus

新增 `eval_sets/real_rag_qa.jsonl`，至少 60 筆：

| 類型 | 數量 |
| --- | --- |
| 知識與檢索 | 15 |
| AI代理系統 | 15 |
| LLM推理與評估 | 15 |
| AI安全 | 10 |
| 開發者工具與框架 | 5 |

每筆格式：

```json
{
  "id": "real-rag-001",
  "question": "GraphRAG 和 VectorRAG 的差異是什麼？",
  "expected_topics": ["知識與檢索"],
  "expected_keywords": ["GraphRAG", "VectorRAG"],
  "expected_files": [],
  "answer_type": "synthesis"
}
```

### 2. Retrieval Benchmark

新增：

```bash
rdos benchmark retrieval --embedding-provider local-bge-m3
```

輸出 metrics：

- Recall@3
- Recall@5
- MRR
- keyword hit rate
- semantic hit rate
- hybrid hit rate
- no-answer accuracy
- latency p50 / p95

### 3. Hybrid Search Tuning

`configs/rag.yaml` 支援：

```yaml
retrieval:
  vector_top_k: 20
  keyword_top_k: 20
  rerank_top_k: 8
  rrf_k: 60
  semantic_weight: 0.6
  keyword_weight: 0.4
  min_score_threshold: 0.05
```

### 4. Query Rewrite

新增 `src/rdos/rag/query_rewriter.py`：

- 保留英文技術詞（AgentTrace、GraphRAG、RAG）
- 提取中文關鍵詞（多智能體、因果圖、追蹤）
- 支援 alias expansion（可由 `configs/rag.yaml` 設定 aliases）

範例：

```
原 query: AgentTrace 多智能體因果圖追蹤
rewritten: ["AgentTrace", "多智能體", "因果圖", "trace", "flight recorder"]
```

### 5. No-Answer Handling

當 retrieval score 低於 threshold 或 citation validation 不足時，`ask` workflow **不可硬答**，必須回：

> 目前資料庫沒有足夠證據回答

## 需求

1. 新增 `eval_sets/real_rag_qa.jsonl`，至少 60 筆，覆蓋上列 5 個 topic。
2. 每筆包含 `id` / `question` / `expected_topics` / `expected_keywords` / `expected_files`(optional) / `answer_type`。
3. 新增 `rdos benchmark retrieval`。
4. benchmark 輸出 Recall@3 / Recall@5 / MRR / 三種 hit rate / no-answer accuracy / latency p50/p95。
5. `configs/rag.yaml` 支援 tuning（vector_top_k / keyword_top_k / rerank_top_k / rrf_k / semantic_weight / keyword_weight / min_score_threshold）。
6. 新增 `query_rewriter.py`：保留英文技術詞、提取中文關鍵詞、支援 alias expansion、可由 config 設定 aliases。
7. 新增 no-answer handling：score 低於 threshold 或 citation validation 不足時回 `insufficient_evidence`。
8. eval report 加入 retrieval benchmark section。
9. trace 記錄：`original_query` / `rewritten_queries` / `semantic_results` / `keyword_results` / `hybrid_results` / `retrieval_latency_ms` / `no_answer_triggered`。
10. 不要新增 Web UI。
11. 不要改 privacy policy。
12. tests 不依賴真實 clawd-research，但 real benchmark 可需要本機資料。

## 驗收重點

這批**不要只看 PASS，要看品質**。

必須搜得準的 query：

- GraphRAG / VectorRAG / 層次化摘要
- AgentTrace / 多智能體 / 因果圖追蹤
- Argus-LLM / 六維度輸出評估
- Context Engineering / 記憶與檢索

必須正確 no-answer：

- 完全不存在的 `XYZFakePaper2026`

## 驗收

```bash
uv run pytest
uv run ruff check .
uv run rdos benchmark retrieval --embedding-provider local-bge-m3
uv run rdos search "AgentTrace 多智能體因果圖追蹤" --embedding-provider local-bge-m3
uv run rdos search "GraphRAG VectorRAG 層次化摘要"   --embedding-provider local-bge-m3

uv run rdos ask "我有沒有整理過 AgentTrace？" \
  --llm-mode local --embedding-provider local-bge-m3

uv run rdos ask "我有沒有整理過完全不存在的 XYZFakePaper2026？" \
  --llm-mode local --embedding-provider local-bge-m3
```

## 完成後輸出

1. 修改檔案
2. retrieval benchmark 結果
3. query rewrite 策略
4. no-answer 規則
5. 驗收結果
6. 下一個建議 batch

## Commit

```
feat(batch-13): harden retrieval quality on real research corpus
```
