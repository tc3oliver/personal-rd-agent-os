"""Hybrid retriever: semantic + keyword + metadata filter + RRF merge.

Batch 13 additions:
- query rewrite (alias expansion)
- vector_top_k / keyword_top_k / rerank_top_k from config
- min_score_threshold + no-answer flag
- RetrievalResult.no_answer_triggered
- RetrievalResult.rewrite_info
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rdos.config import RdosConfig
from rdos.rag.embedding import EmbeddingProvider, build_embedding_provider
from rdos.rag.hybrid_search import (
    RetrievalFilters,
    reciprocal_rank_fusion,
)
from rdos.rag.query_rewriter import rewrite_query
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.document import DocumentChunk


@dataclass
class RetrievalResult:
    chunks: list[DocumentChunk]
    raw_semantic: list[tuple[str, float]]
    raw_keyword: list[tuple[str, float]]
    merged_scores: dict[str, float]
    rewrite_info: dict = field(default_factory=dict)
    no_answer_triggered: bool = False
    retrieval_latency_ms: int = 0

    @property
    def top_chunk(self) -> DocumentChunk | None:
        return self.chunks[0] if self.chunks else None


class HybridRetriever:
    def __init__(
        self,
        *,
        sqlite_store: SqliteMetadataStore,
        vector_store: LanceVectorStore,
        embedding: EmbeddingProvider | None = None,
        config: RdosConfig | None = None,
    ) -> None:
        self.store = sqlite_store
        self.vectors = vector_store
        self.config = config or _load_default_config()
        self.embedding = embedding or build_embedding_provider(
            provider=self.config.models.embedding.provider,
            dim=self.config.models.embedding.dim or self.config.rag.embedding.dim,
        )

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        import time

        started = time.perf_counter()
        k = top_k or self.config.rag.retrieval.top_k
        f = filters or RetrievalFilters()

        rewrite_info: dict = {}
        primary_query = query
        if self.config.rag.retrieval.enable_query_rewrite:
            rewrite_info = rewrite_query(query, cfg=self.config.rag)
            primary_query = rewrite_info["rewritten_queries"][0]

        # ----- Semantic -----
        query_vec = self.embedding.embed_one(primary_query)
        semantic = self.vectors.search(
            query_vec,
            top_k=self.config.rag.retrieval.vector_top_k,
        )

        # ----- Keyword -----
        keyword = self.store.keyword_search(
            primary_query,
            limit=self.config.rag.retrieval.keyword_top_k,
        )

        # ----- Merge -----
        merged = reciprocal_rank_fusion(
            semantic,
            keyword,
            k=self.config.rag.retrieval.rrf_k,
            semantic_weight=self.config.rag.retrieval.semantic_weight,
            keyword_weight=self.config.rag.retrieval.keyword_weight,
        )

        ranked_ids = [
            cid
            for cid, _ in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
        ]
        rerank_top = self.config.rag.retrieval.rerank_top_k
        chunks: list[DocumentChunk] = []
        for cid in ranked_ids:
            chunk = self.store.get_chunk(cid)
            if chunk is None:
                continue
            if not _matches_filters(chunk, f):
                continue
            chunk.score = float(merged.get(cid, 0.0))
            chunks.append(chunk)
            if len(chunks) >= max(k, rerank_top):
                break

        chunks = chunks[: max(k, rerank_top)]

        threshold = self.config.rag.retrieval.min_score_threshold
        no_answer_threshold = self.config.rag.retrieval.no_answer_threshold
        top_score = chunks[0].score if chunks else 0.0
        no_answer = bool(chunks) and top_score < no_answer_threshold
        if no_answer:
            chunks = []

        # Apply min_score_threshold as a soft cut (kept in result for caller).
        if chunks and threshold > 0:
            chunks = [c for c in chunks if (c.score or 0) >= threshold] or chunks

        latency_ms = int((time.perf_counter() - started) * 1000)
        return RetrievalResult(
            chunks=chunks[:k],
            raw_semantic=semantic,
            raw_keyword=keyword,
            merged_scores=merged,
            rewrite_info=rewrite_info,
            no_answer_triggered=no_answer,
            retrieval_latency_ms=latency_ms,
        )


def _load_default_config() -> RdosConfig:
    from rdos.config import get_config

    return get_config()


def _matches_filters(chunk: DocumentChunk, f: RetrievalFilters) -> bool:
    if f.privacy_levels and chunk.privacy_level not in f.privacy_levels:
        return False
    if f.tags and not set(chunk.tags).intersection(f.tags):
        return False
    if f.folder and f.folder not in chunk.file_path:
        return False
    if f.date_from and chunk.date and chunk.date < f.date_from:
        return False
    if f.date_to and chunk.date and chunk.date > f.date_to:
        return False
    return True
