"""RAG Recall@K eval — does the retriever put an expected doc in top-K?"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rdos.config import RdosConfig
from rdos.rag.embedding import EmbeddingProvider, build_embedding_provider
from rdos.rag.retriever import HybridRetriever
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def evaluate_rag(
    cfg: RdosConfig,
    *,
    eval_set: str | Path = "eval_sets/rag_qa.jsonl",
    k: int = 5,
    embedding: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    """Returns metrics dict with recall_at_k, sample_count, and per-sample results."""
    samples = load_jsonl(eval_set)
    if not samples:
        return {"metric": "rag_recall_at_5", "value": 0.0, "samples": 0, "results": []}

    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(
        cfg.rag.storage.lancedb_path,
        dim=cfg.models.embedding.dim or cfg.rag.embedding.dim,
    )
    emb = embedding or build_embedding_provider(
        provider=cfg.models.embedding.provider,
        dim=cfg.models.embedding.dim or cfg.rag.embedding.dim,
    )
    retriever = HybridRetriever(
        sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg
    )

    hits = 0
    results: list[dict[str, Any]] = []
    for sample in samples:
        query = sample["query"]
        expected_docs = set(sample.get("expected_doc_ids", []))
        result = retriever.search(query, top_k=k)
        retrieved_docs = {c.file_path for c in result.chunks}
        is_hit = bool(expected_docs & retrieved_docs)
        hits += int(is_hit)
        results.append(
            {
                "query": query,
                "expected_doc_ids": sorted(expected_docs),
                "retrieved_doc_ids": sorted(retrieved_docs),
                "hit": is_hit,
            }
        )

    store.close()
    return {
        "metric": "rag_recall_at_5",
        "value": hits / len(samples),
        "samples": len(samples),
        "results": results,
    }
