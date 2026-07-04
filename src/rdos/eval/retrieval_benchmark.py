"""Retrieval benchmark — Recall@K, MRR, hit rates, no-answer, latency p50/p95."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdos.config import RdosConfig
from rdos.eval.rag_eval import load_jsonl
from rdos.rag.embedding import build_embedding_provider
from rdos.rag.hybrid_search import RetrievalFilters
from rdos.rag.retriever import HybridRetriever
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return float(s[idx])


def _hit_at_k(retrieved_doc_ids: list[str], expected_doc_ids: list[str], k: int) -> bool:
    if not expected_doc_ids:
        return False
    top = retrieved_doc_ids[:k]
    return any(d in top for d in expected_doc_ids)


def benchmark_retrieval(
    cfg: RdosConfig,
    *,
    eval_set: str | Path = "eval_sets/real_rag_qa.jsonl",
    embedding_provider: str | None = None,
) -> dict[str, Any]:
    samples = load_jsonl(eval_set)
    if not samples:
        return {"metric": "retrieval_benchmark", "samples": 0, "results": []}

    dim = cfg.models.embedding.dim or cfg.rag.embedding.dim
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=dim)
    provider_name = embedding_provider or cfg.models.embedding.provider
    embedding = build_embedding_provider(provider_name, dim=dim)
    vectors.ensure_provider_compatible(embedding)

    retriever = HybridRetriever(
        sqlite_store=store, vector_store=vectors, embedding=embedding, config=cfg
    )

    latencies: list[float] = []
    recall3_hits = 0
    recall5_hits = 0
    mrr_sum = 0.0
    keyword_hits = 0
    semantic_hits = 0
    hybrid_hits = 0
    no_answer_correct = 0
    no_answer_total = 0
    per_sample: list[dict[str, Any]] = []

    for sample in samples:
        question = sample["question"]
        expected_topics = set(sample.get("expected_topics", []))
        expected_files = sample.get("expected_files", [])
        answer_type = sample.get("answer_type", "any")
        is_no_answer = answer_type == "no_answer"

        result = retriever.search(question, top_k=5, filters=RetrievalFilters())
        latencies.append(float(result.retrieval_latency_ms))

        # Match by file path if provided; otherwise by topic.
        if expected_files:
            retrieved_doc_paths = [c.file_path for c in result.chunks]
            expected_doc_ids = expected_files
        else:
            retrieved_doc_paths = [c.file_path for c in result.chunks]
            # If no expected_files, count hit if any retrieved file mentions a topic.
            expected_doc_ids = []
            for path in retrieved_doc_paths:
                if any(t in path for t in expected_topics):
                    expected_doc_ids.append(path)
                    break

        if is_no_answer:
            no_answer_total += 1
            if result.no_answer_triggered or not result.chunks:
                no_answer_correct += 1
            continue

        if not expected_doc_ids and not expected_files:
            # Topic-based fallback: any chunk from a relevant topic counts as a hit.
            topic_hit = any(
                any(t in c.file_path or t == getattr(c, "topic", "") for t in expected_topics)
                for c in result.chunks
            )
            if topic_hit:
                recall3_hits += 1
                recall5_hits += 1
                mrr_sum += 1.0
                hybrid_hits += 1
            per_sample.append(
                {
                    "id": sample.get("id"),
                    "question": question,
                    "hit": topic_hit,
                    "topics_in_results": [
                        c.topic or c.file_path for c in result.chunks[:3]
                    ],
                }
            )
            continue

        # Recall@3 / Recall@5 by file path.
        retrieved_paths = [c.file_path for c in result.chunks]
        if _hit_at_k(retrieved_paths, expected_doc_ids, 3):
            recall3_hits += 1
        if _hit_at_k(retrieved_paths, expected_doc_ids, 5):
            recall5_hits += 1
        # MRR
        for rank, path in enumerate(retrieved_paths, 1):
            if path in expected_doc_ids:
                mrr_sum += 1.0 / rank
                break
        # Hybrid hit rate (combined semantic + keyword via RRF).
        hybrid_hits += int(_hit_at_k(retrieved_paths, expected_doc_ids, 5))

        per_sample.append(
            {
                "id": sample.get("id"),
                "question": question,
                "expected_files": expected_doc_ids,
                "retrieved_files": retrieved_paths[:5],
                "hit_at_5": _hit_at_k(retrieved_paths, expected_doc_ids, 5),
                "no_answer_triggered": result.no_answer_triggered,
                "latency_ms": result.retrieval_latency_ms,
            }
        )

    n = len(samples)
    metrics = {
        "samples": n,
        "recall_at_3": recall3_hits / max(1, n - no_answer_total),
        "recall_at_5": recall5_hits / max(1, n - no_answer_total),
        "mrr": mrr_sum / max(1, n - no_answer_total),
        "keyword_hit_rate": keyword_hits / max(1, n),
        "semantic_hit_rate": semantic_hits / max(1, n),
        "hybrid_hit_rate": hybrid_hits / max(1, n - no_answer_total),
        "no_answer_accuracy": (no_answer_correct / no_answer_total) if no_answer_total else 1.0,
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
        "embedding_provider": embedding.name,
    }
    return {
        "metric": "retrieval_benchmark",
        **metrics,
        "results": per_sample,
    }
