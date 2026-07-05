"""Per-collection no-answer threshold calibration.

For each collection, run real queries against indexed data and find a
threshold below which retrieval is untrustworthy.

Strategy:
  - Run real eval set (synthesis queries) → collect top_score distribution.
  - Run no-answer eval set → collect top_score distribution.
  - Threshold = (real_p5 + no_answer_p95) / 2
  - If real and no_answer distributions overlap heavily, threshold = real_p5.
"""

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


def calibrate_thresholds(
    cfg: RdosConfig,
    *,
    real_eval_set: str | Path = "eval_sets/real_rag_qa.jsonl",
    no_answer_eval_set: str | Path = "eval_sets/no_answer.jsonl",
    embedding_provider: str | None = None,
) -> dict[str, Any]:
    real = [s for s in load_jsonl(real_eval_set) if s.get("answer_type") != "no_answer"]
    no_answer = load_jsonl(no_answer_eval_set)

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

    real_scores: list[float] = []
    na_scores: list[float] = []
    for s in real:
        r = retriever.search(s["question"], top_k=5, filters=RetrievalFilters())
        if r.chunks:
            real_scores.append(max(c.score or 0.0 for c in r.chunks))
    for s in no_answer:
        r = retriever.search(s["question"], top_k=5, filters=RetrievalFilters())
        if r.chunks:
            na_scores.append(max(c.score or 0.0 for c in r.chunks))

    store.close()

    def _percentile(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        idx = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
        return float(s[idx])

    real_p5 = _percentile(real_scores, 5)
    real_p50 = _percentile(real_scores, 50)
    real_p95 = _percentile(real_scores, 95)
    na_p95 = _percentile(na_scores, 95)
    # Threshold: midpoint between real_p5 (worst real) and na_p95 (best fake).
    # If overlap, use real_p5 to avoid false positives.
    midpoint = (real_p5 + na_p95) / 2
    threshold = min(midpoint, real_p5) if real_scores else midpoint

    return {
        "real_samples": len(real_scores),
        "no_answer_samples": len(na_scores),
        "real_top_score_p5": real_p5,
        "real_top_score_p50": real_p50,
        "real_top_score_p95": real_p95,
        "no_answer_top_score_p95": na_p95,
        "recommended_threshold": threshold,
        "note": (
            "Set configs/rag.yaml:retrieval.no_answer_threshold to "
            f"{threshold:.4f} for this collection+provider."
        ),
    }
