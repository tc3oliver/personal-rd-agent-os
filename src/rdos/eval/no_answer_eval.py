"""No-answer evaluator — measure false-positive and false-negative rate."""

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


def evaluate_no_answer(
    cfg: RdosConfig,
    *,
    eval_set: str | Path = "eval_sets/no_answer.jsonl",
    embedding_provider: str | None = None,
    real_eval_set: str | Path = "eval_sets/real_rag_qa.jsonl",
) -> dict[str, Any]:
    """Measure no-answer accuracy (should trigger) and false-positive rate (should not).

    `eval_set` — cases that SHOULD trigger no-answer.
    `real_eval_set` — synthesis queries that SHOULD NOT trigger no-answer.
    """
    samples = load_jsonl(eval_set)
    real_samples = [s for s in load_jsonl(real_eval_set) if s.get("answer_type") != "no_answer"]

    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    dim = cfg.models.embedding.dim or cfg.rag.embedding.dim
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=dim)
    emb = build_embedding_provider(
        embedding_provider or cfg.models.embedding.provider, dim=dim
    )
    vectors.ensure_provider_compatible(emb)
    retriever = HybridRetriever(
        sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg
    )

    # Cases that SHOULD be no-answer
    correct_no_answer = 0
    for s in samples:
        result = retriever.search(s["question"], top_k=5, filters=RetrievalFilters())
        if result.no_answer_triggered or not result.chunks:
            correct_no_answer += 1

    # Cases that SHOULD NOT be no-answer (real synthesis queries)
    false_no_answer = 0
    for s in real_samples:
        result = retriever.search(s["question"], top_k=5, filters=RetrievalFilters())
        if result.no_answer_triggered or not result.chunks:
            false_no_answer += 1

    store.close()
    no_answer_accuracy = correct_no_answer / len(samples) if samples else 0.0
    false_no_answer_rate = (
        false_no_answer / len(real_samples) if real_samples else 0.0
    )

    return {
        "no_answer_samples": len(samples),
        "no_answer_accuracy": no_answer_accuracy,
        "real_samples": len(real_samples),
        "false_no_answer_rate": false_no_answer_rate,
        "results": {
            "correct_no_answer": correct_no_answer,
            "false_no_answer": false_no_answer,
        },
    }
