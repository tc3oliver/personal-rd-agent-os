"""Tests for the indexing pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.rag.embedding import FakeEmbeddingProvider
from rdos.rag.indexer import index_directory
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore


@pytest.fixture()
def isolated_workspace(tmp_path: Path) -> Path:
    return tmp_path


def test_index_creates_stores(isolated_workspace: Path, sample_notes_dir: Path) -> None:
    sqlite_path = isolated_workspace / "rdos.db"
    lancedb_path = isolated_workspace / "lancedb"

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

    cfg = RdosConfig(
        models=ModelsConfig(embedding=EmbeddingConfig(provider="fake", dim=64)),
        rag=RagConfig(
            chunking=ChunkingConfig(target_min_tokens=50, target_max_tokens=150),
            storage=StorageConfig(
                sqlite_path=str(sqlite_path),
                lancedb_path=str(lancedb_path),
            ),
            embedding=EmbeddingRuntimeConfig(dim=64),
            retrieval=RetrievalConfig(),
        ),
    )

    stats = index_directory(sample_notes_dir, config=cfg)
    assert stats.documents_indexed >= 5
    assert stats.chunks_inserted > 0
    assert sqlite_path.exists()
    assert lancedb_path.exists()


def test_index_is_idempotent(isolated_workspace: Path, sample_notes_dir: Path) -> None:
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

    cfg = RdosConfig(
        models=ModelsConfig(embedding=EmbeddingConfig(provider="fake", dim=64)),
        rag=RagConfig(
            chunking=ChunkingConfig(target_min_tokens=50, target_max_tokens=150),
            storage=StorageConfig(
                sqlite_path=str(isolated_workspace / "rdos.db"),
                lancedb_path=str(isolated_workspace / "lancedb"),
            ),
            embedding=EmbeddingRuntimeConfig(dim=64),
            retrieval=RetrievalConfig(),
        ),
    )

    first = index_directory(sample_notes_dir, config=cfg)
    second = index_directory(sample_notes_dir, config=cfg)

    assert first.chunks_inserted > 0
    assert second.chunks_inserted == 0
    assert second.chunks_skipped == first.chunks_inserted
    # Re-index should produce identical chunk counts in stores
    assert first.documents_indexed == second.documents_indexed


def test_fake_embedding_provider_used_by_default(
    isolated_workspace: Path, sample_notes_dir: Path
) -> None:
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

    cfg = RdosConfig(
        models=ModelsConfig(embedding=EmbeddingConfig(provider="fake", dim=32)),
        rag=RagConfig(
            chunking=ChunkingConfig(target_min_tokens=50, target_max_tokens=150),
            storage=StorageConfig(
                sqlite_path=str(isolated_workspace / "rdos.db"),
                lancedb_path=str(isolated_workspace / "lancedb"),
            ),
            embedding=EmbeddingRuntimeConfig(dim=32),
            retrieval=RetrievalConfig(),
        ),
    )

    stats = index_directory(sample_notes_dir, config=cfg)
    assert stats.chunks_inserted > 0

    vs = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=32)
    assert vs.count() == stats.chunks_inserted

    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    chunks = store.all_chunks()
    assert len(chunks) == stats.chunks_inserted
    store.close()


def test_custom_embedding_provider_injected(isolated_workspace: Path, sample_notes_dir: Path) -> None:
    from rdos.config import (
        ChunkingConfig,
        EmbeddingRuntimeConfig,
        RagConfig,
        RdosConfig,
        RetrievalConfig,
        StorageConfig,
    )

    cfg = RdosConfig(
        rag=RagConfig(
            chunking=ChunkingConfig(target_min_tokens=50, target_max_tokens=150),
            storage=StorageConfig(
                sqlite_path=str(isolated_workspace / "rdos.db"),
                lancedb_path=str(isolated_workspace / "lancedb"),
            ),
            embedding=EmbeddingRuntimeConfig(dim=48),
            retrieval=RetrievalConfig(),
        ),
    )

    emb = FakeEmbeddingProvider(dim=48)
    stats = index_directory(sample_notes_dir, config=cfg, embedding=emb)
    assert stats.chunks_inserted > 0


@pytest.fixture()
def sample_notes_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "sample_data" / "notes"
