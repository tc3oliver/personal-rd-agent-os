"""Hybrid retriever: semantic + keyword + metadata filter + RRF merge."""

from __future__ import annotations

from dataclasses import dataclass

from rdos.config import RdosConfig
from rdos.rag.embedding import EmbeddingProvider, build_embedding_provider
from rdos.rag.hybrid_search import (
    RetrievalFilters,
    reciprocal_rank_fusion,
)
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.document import DocumentChunk


@dataclass
class RetrievalResult:
    chunks: list[DocumentChunk]
    raw_semantic: list[tuple[str, float]]
    raw_keyword: list[tuple[str, float]]
    merged_scores: dict[str, float]

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
        k = top_k or self.config.rag.retrieval.top_k
        f = filters or RetrievalFilters()

        # ----- Semantic -----
        query_vec = self.embedding.embed_one(query)
        semantic = self.vectors.search(query_vec, top_k=k * 4)

        # ----- Keyword -----
        keyword = self.store.keyword_search(query, limit=k * 4)

        # ----- Merge -----
        merged = reciprocal_rank_fusion(
            semantic,
            keyword,
            k=self.config.rag.retrieval.rrf_k,
            semantic_weight=self.config.rag.retrieval.semantic_weight,
            keyword_weight=self.config.rag.retrieval.keyword_weight,
        )

        # Rank by merged score, then hydrate + filter
        ranked_ids = [cid for cid, _ in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)]
        chunks: list[DocumentChunk] = []
        for cid in ranked_ids:
            chunk = self.store.get_chunk(cid)
            if chunk is None:
                continue
            if not _matches_filters(chunk, f):
                continue
            chunk.score = float(merged.get(cid, 0.0))
            chunks.append(chunk)
            if len(chunks) >= k:
                break

        return RetrievalResult(
            chunks=chunks,
            raw_semantic=semantic,
            raw_keyword=keyword,
            merged_scores=merged,
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
