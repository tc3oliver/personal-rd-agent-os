"""Tests for the JSONL trace store."""

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
from rdos.graph.research_memory_graph import ResearchMemoryGraph
from rdos.llm.provider import StubLLMAdapter
from rdos.rag.embedding import FakeEmbeddingProvider
from rdos.rag.indexer import index_directory
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.trace import TraceError, TraceMetrics
from rdos.trace.trace_logger import Timer, new_run_id, now_iso, record_run
from rdos.trace.trace_store import JsonlTraceStore, build_record_from_state


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
            }
            | {
                "public": PrivacyRule(
                    allow_external_model=True, requires_user_confirmation=False
                )
            },
        ),
        rag=RagConfig(
            chunking=ChunkingConfig(target_min_tokens=30, target_max_tokens=120),
            storage=StorageConfig(
                sqlite_path=str(tmp_path / "rdos.db"),
                lancedb_path=str(tmp_path / "lancedb"),
            ),
            embedding=EmbeddingRuntimeConfig(dim=64),
            retrieval=RetrievalConfig(),
        ),
    )
    index_directory(sample_notes_dir, config=cfg)
    return cfg


def test_trace_store_append_and_list(tmp_path: Path) -> None:
    store = JsonlTraceStore(tmp_path / "runs.jsonl")

    from rdos.schemas.trace import TraceRecord

    rec = TraceRecord(
        run_id="abc",
        timestamp="2026-07-05T00:00:00Z",
        task_type="research_memory",
        user_query="q",
    )
    store.append(rec)
    store.append(
        TraceRecord(
            run_id="def",
            timestamp="2026-07-05T01:00:00Z",
            task_type="research_memory",
            user_query="q2",
        )
    )

    runs = store.list_runs()
    assert len(runs) == 2
    # Most-recent first
    assert runs[0].run_id == "def"
    assert runs[1].run_id == "abc"

    fetched = store.get("abc")
    assert fetched is not None
    assert fetched.user_query == "q"


def test_trace_record_built_from_state(indexed_config: RdosConfig, tmp_path: Path) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    graph = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )
    state = graph.run("RAG filtering")

    record = build_record_from_state(
        state,
        run_id="r1",
        timestamp="2026-07-05T00:00:00Z",
        metrics=TraceMetrics(latency_ms=42),
        errors=[TraceError(code="x", message="y")],
    )
    assert record.task_type == "research_memory"
    assert record.user_query == "RAG filtering"
    assert record.privacy_decision is not None
    assert record.model_routing_decision is not None
    assert record.final_answer is not None
    assert record.metrics.latency_ms == 42
    assert record.errors[0].code == "x"
    store.close()


def test_record_run_helper_writes_jsonl(indexed_config: RdosConfig, tmp_path: Path) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    graph = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )
    state = graph.run("RAG filtering")

    trace_path = tmp_path / "runs.jsonl"
    trace = JsonlTraceStore(trace_path)
    timer = Timer()
    rid = record_run(trace, state, timer=timer)

    assert rid  # uuid hex
    listed = trace.list_runs()
    assert len(listed) == 1
    assert listed[0].run_id == rid
    assert listed[0].metrics.latency_ms is not None
    store.close()


def test_record_run_round_trip_preserves_citations(
    indexed_config: RdosConfig, tmp_path: Path
) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = FakeEmbeddingProvider(dim=64)
    llm = StubLLMAdapter()
    graph = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )
    state = graph.run("RAG filtering")

    trace = JsonlTraceStore(tmp_path / "runs.jsonl")
    rid = record_run(trace, state)
    fetched = trace.get(rid)
    assert fetched is not None
    assert fetched.final_answer is not None
    if state.get("citations"):
        assert len(fetched.citations) == len(state["citations"])
    store.close()


def test_helpers_produce_unique_ids_and_iso_timestamp() -> None:
    a = new_run_id()
    b = new_run_id()
    assert a != b
    ts = now_iso()
    assert "T" in ts


@pytest.fixture()
def sample_notes_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "sample_data" / "notes"
