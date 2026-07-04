"""Tests for the research_memory_graph."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.config import (
    ChunkingConfig,
    EmbeddingConfig,
    EmbeddingRuntimeConfig,
    ModelsConfig,
    PrivacyPolicyConfig,
    PrivacyRule,
    ProfileConfig,
    RagConfig,
    RdosConfig,
    RetrievalConfig,
    StorageConfig,
)
from rdos.graph.research_memory_graph import ResearchMemoryGraph, build_research_memory_graph
from rdos.graph.root_graph import run_task
from rdos.llm.provider import StubLLMAdapter
from rdos.rag.embedding import FakeEmbeddingProvider
from rdos.rag.indexer import index_directory
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.privacy import PrivacyLevel


@pytest.fixture()
def indexed_config(tmp_path: Path, sample_notes_dir: Path) -> RdosConfig:
    cfg = RdosConfig(
        models=ModelsConfig(
            profiles={
                "local_fast": ProfileConfig(provider="local", model="stub"),
                "cloud_reasoning": ProfileConfig(provider="cloud", model="gpt-x"),
            },
            task_defaults={"research_memory": "local_fast"},
            embedding=EmbeddingConfig(provider="fake", dim=64),
        ),
        privacy_policy=PrivacyPolicyConfig(
            privacy_order=["public", "private_summary", "private_raw", "company_sensitive"],
            default_chunk_privacy="private_raw",
            default_query_privacy="private_raw",
            rules={
                "public": PrivacyRule(allow_external_model=True, requires_user_confirmation=False),
                "private_summary": PrivacyRule(
                    allow_external_model=True, requires_user_confirmation=True
                ),
                "private_raw": PrivacyRule(
                    allow_external_model=False, requires_user_confirmation=False
                ),
                "company_sensitive": PrivacyRule(
                    allow_external_model=False, requires_user_confirmation=False
                ),
            },
            query_privacy_hints={"public": ["definition"], "company_sensitive": ["roadmap"]},
        ),
        rag=RagConfig(
            chunking=ChunkingConfig(target_min_tokens=30, target_max_tokens=120),
            storage=StorageConfig(
                sqlite_path=str(tmp_path / "rdos.db"),
                lancedb_path=str(tmp_path / "lancedb"),
            ),
            embedding=EmbeddingRuntimeConfig(dim=64),
            retrieval=RetrievalConfig(top_k=3, semantic_weight=0.6, keyword_weight=0.4),
        ),
    )
    index_directory(sample_notes_dir, config=cfg)
    return cfg


def test_graph_runs_11_nodes_and_produces_answer(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter(model="stub", provider="stub")
    graph = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )

    state = graph.run("RAG filtering")

    assert state["task_type"] == "research_memory"
    assert "privacy_decision" in state
    assert "model_routing" in state
    assert "retrieved_chunks" in state
    assert state["final_answer"] is not None
    assert state["final_answer"].selected_model_profile == "local_fast"
    assert state["final_answer"].effective_privacy_level in (
        PrivacyLevel.private_raw,
        PrivacyLevel.company_sensitive,
        PrivacyLevel.private_summary,
    )
    store.close()


def test_graph_uses_local_when_query_is_private(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    graph = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )

    state = graph.run("roadmap draft")  # company_sensitive hint
    routing = state["model_routing"]
    assert routing.provider == "local"
    assert routing.allows_external_model is False
    store.close()


def test_graph_citations_are_validated(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    graph = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )

    state = graph.run("RAG filtering")
    report = state["citation_report"]
    assert report is not None
    if state["citations"]:
        # Citations produced from retrieved context must be valid
        assert report.all_valid
    store.close()


def test_root_graph_dispatches_research_memory(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    graph = build_research_memory_graph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )
    state = run_task("research_memory", "RAG filtering", graph)
    assert state["final_answer"] is not None
    store.close()


def test_root_graph_rejects_unknown_task(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    graph = build_research_memory_graph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb
    )
    with pytest.raises(NotImplementedError):
        run_task("code_analysis", "x", graph)
    store.close()


@pytest.fixture()
def sample_notes_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "sample_data" / "notes"
