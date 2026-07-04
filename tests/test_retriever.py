"""Tests for hybrid retriever, citation builder, citation validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.config import (
    ChunkingConfig,
    EmbeddingConfig,
    EmbeddingRuntimeConfig,
    ModelsConfig,
    RagConfig,
    RdosConfig,
    RetrievalConfig,
    StorageConfig,
)
from rdos.rag.citation_builder import CitationBuilder
from rdos.rag.citation_validator import CitationValidator
from rdos.rag.embedding import FakeEmbeddingProvider
from rdos.rag.hybrid_search import RetrievalFilters, reciprocal_rank_fusion
from rdos.rag.indexer import index_directory
from rdos.rag.retriever import HybridRetriever
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.citation import Citation
from rdos.schemas.document import DocumentChunk
from rdos.schemas.privacy import PrivacyLevel


@pytest.fixture()
def indexed_workspace(tmp_path: Path, sample_notes_dir: Path) -> RdosConfig:
    cfg = RdosConfig(
        models=ModelsConfig(embedding=EmbeddingConfig(provider="fake", dim=64)),
        rag=RagConfig(
            chunking=ChunkingConfig(target_min_tokens=30, target_max_tokens=120),
            storage=StorageConfig(
                sqlite_path=str(tmp_path / "rdos.db"),
                lancedb_path=str(tmp_path / "lancedb"),
            ),
            embedding=EmbeddingRuntimeConfig(dim=64),
            retrieval=RetrievalConfig(top_k=5, semantic_weight=0.6, keyword_weight=0.4),
        ),
    )
    index_directory(sample_notes_dir, config=cfg)
    return cfg


def test_rrf_merges_ranks() -> None:
    semantic = [("a", 0.9), ("b", 0.8), ("c", 0.7)]
    keyword = [("b", -1.0), ("a", -2.0)]
    scores = reciprocal_rank_fusion(semantic, keyword, k=60)
    # both 'a' and 'b' appear in both lists → should outrank 'c'
    assert scores["a"] > scores["c"]
    assert scores["b"] > scores["c"]


def test_retriever_returns_chunks(indexed_workspace: RdosConfig) -> None:
    cfg = indexed_workspace
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    retriever = HybridRetriever(sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg)

    result = retriever.search("RAG filtering", top_k=5)
    assert result.chunks
    assert all(isinstance(c, DocumentChunk) for c in result.chunks)
    # Scores are populated and sorted descending
    scores = [c.score for c in result.chunks if c.score is not None]
    assert scores == sorted(scores, reverse=True)
    store.close()


def test_retriever_metadata_filter_privacy(indexed_workspace: RdosConfig) -> None:
    cfg = indexed_workspace
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    retriever = HybridRetriever(sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg)

    result = retriever.search(
        "agent",
        top_k=10,
        filters=RetrievalFilters(privacy_levels=[PrivacyLevel.public]),
    )
    assert all(c.privacy_level == PrivacyLevel.public for c in result.chunks)
    store.close()


def test_citation_builder_creates_citations(indexed_workspace: RdosConfig) -> None:
    cfg = indexed_workspace
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    retriever = HybridRetriever(sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg)

    result = retriever.search("RAG filtering", top_k=3)
    citations = CitationBuilder(max_citations=3).build("RAG filtering", result)
    assert citations
    for c in citations:
        assert c.chunk_id
        assert c.title
        assert c.chunk_hash
        assert 0 < len(c.quote) <= 200
    store.close()


def test_citation_validator_accepts_valid(indexed_workspace: RdosConfig) -> None:
    cfg = indexed_workspace
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    retriever = HybridRetriever(sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg)

    result = retriever.search("RAG filtering", top_k=3)
    citations = CitationBuilder(max_citations=3).build("RAG filtering", result)

    validator = CitationValidator(store)
    report = validator.validate_many(citations, result.chunks)
    assert report.all_valid
    assert report.valid_count == report.total_count
    store.close()


def test_citation_validator_rejects_hash_mismatch(indexed_workspace: RdosConfig) -> None:
    cfg = indexed_workspace
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    retriever = HybridRetriever(sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg)

    result = retriever.search("RAG filtering", top_k=3)
    if not result.chunks:
        pytest.skip("retriever returned nothing")
    chunk = result.chunks[0]
    bad = Citation(
        chunk_id=chunk.chunk_id,
        doc_id=chunk.doc_id,
        file_path=chunk.file_path,
        title=chunk.title,
        heading_path=list(chunk.heading_path),
        quote="...",
        chunk_hash="WRONG HASH",
    )
    validator = CitationValidator(store)
    res = validator.validate(bad, result.chunks)
    assert res.chunk_exists
    assert not res.hash_matches
    assert not res.is_valid
    assert res.error == "chunk_hash mismatch"
    store.close()


def test_citation_validator_rejects_unknown_chunk(indexed_workspace: RdosConfig) -> None:
    cfg = indexed_workspace
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    fake = Citation(
        chunk_id="doesnotexist",
        doc_id="nope",
        file_path="x",
        title="x",
        heading_path=[],
        quote="...",
        chunk_hash="x",
    )
    validator = CitationValidator(store)
    res = validator.validate(fake, [])
    assert not res.chunk_exists
    assert not res.is_valid
    store.close()


@pytest.fixture()
def sample_notes_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "sample_data" / "notes"
