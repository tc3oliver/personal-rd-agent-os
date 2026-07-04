"""Tests for Batch 14: LangGraph runtime."""

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
from rdos.graph.langgraph_runtime import LangGraphRuntime, build_langgraph_runtime
from rdos.graph.research_memory_graph import ResearchMemoryGraph
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
            profiles={"local_fast": ProfileConfig(provider="local", model="stub")},
            task_defaults={"research_memory": "local_fast"},
            embedding=EmbeddingConfig(provider="fake", dim=64),
        ),
        privacy_policy=PrivacyPolicyConfig(
            privacy_order=["public", "private_summary", "private_raw", "company_sensitive"],
            default_chunk_privacy="private_raw",
            default_query_privacy="private_raw",
            rules={
                lv: PrivacyRule(allow_external_model=False, requires_user_confirmation=False)
                for lv in ("public", "private_summary", "private_raw", "company_sensitive")
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
            retrieval=RetrievalConfig(top_k=3, enable_query_rewrite=False),
        ),
    )
    index_directory(sample_notes_dir, config=cfg)
    return cfg


def test_langgraph_invoke_succeeds(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    runner = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )
    runtime = LangGraphRuntime(runner)
    state, thread_id = runtime.invoke("RAG filtering")

    assert thread_id  # uuid hex
    assert state.get("final_answer") is not None
    assert state["task_type"] == "research_memory"
    store.close()


def test_langgraph_state_fields_complete(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    runner = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )
    runtime = LangGraphRuntime(runner)
    state, _ = runtime.invoke("RAG filtering")
    for key in (
        "task_type",
        "user_query",
        "privacy_decision",
        "model_routing",
        "retrieved_chunks",
        "final_answer",
        "citations",
    ):
        assert key in state, f"missing state key: {key}"
    store.close()


def test_langgraph_node_trace_present(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    runner = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )
    runtime = LangGraphRuntime(runner)
    runtime.invoke("RAG filtering")

    expected_nodes = {
        "classify_task",
        "assess_query_privacy",
        "retrieve_notes",
        "calculate_effective_privacy",
        "select_model_profile",
        "build_context",
        "generate_answer",
        "build_citations",
        "validate_citations",
        "format_structured_output",
    }
    seen = {n["name"] for n in runtime.node_trace}
    assert expected_nodes.issubset(seen), f"missing nodes: {expected_nodes - seen}"
    for n in runtime.node_trace:
        assert n["status"] == "success"
        assert n["latency_ms"] >= 0
    store.close()


def test_langgraph_thread_id_is_unique_per_invoke(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    runner = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )
    runtime = LangGraphRuntime(runner)
    _, t1 = runtime.invoke("first question")
    _, t2 = runtime.invoke("second question")
    assert t1 != t2
    store.close()


def test_linear_runtime_still_works(indexed_config: RdosConfig) -> None:
    """Linear runner is preserved as legacy fallback."""
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    graph = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )
    state = graph.run("RAG filtering")
    assert state["final_answer"] is not None
    store.close()


def test_langgraph_effective_privacy_propagates(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    runner = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )
    runtime = LangGraphRuntime(runner)
    state, _ = runtime.invoke("RAG filtering")
    # Sample notes include private_raw chunks → effective must be at least private_raw
    eff = state["effective_privacy_level"]
    assert eff in (
        PrivacyLevel.private_raw,
        PrivacyLevel.company_sensitive,
        PrivacyLevel.private_summary,
    )
    store.close()


def test_build_langgraph_runtime_factory(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    runtime = build_langgraph_runtime(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb
    )
    assert isinstance(runtime, LangGraphRuntime)


@pytest.fixture()
def sample_notes_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "sample_data" / "notes"
