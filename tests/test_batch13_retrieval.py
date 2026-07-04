"""Tests for Batch 13: query rewrite, no-answer, retrieval benchmark."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.config import (
    RagConfig,
    RetrievalConfig,
)
from rdos.rag.query_rewriter import rewrite_query

# ---- query rewriter ----


def test_rewrite_preserves_english_terms() -> None:
    info = rewrite_query("AgentTrace 多智能體因果圖追蹤")
    tokens = info["tokens"]
    assert "AgentTrace" in tokens
    # CJK characters appear in tokens too
    assert any("多" in t for t in tokens)


def test_rewrite_alias_expansion() -> None:
    info = rewrite_query("AgentTrace")
    expansions = info["alias_expansions"]
    # alias table includes "flight recorder"
    assert any("flight" in e.lower() for e in expansions)


def test_rewrite_returns_multiple_queries() -> None:
    info = rewrite_query("GraphRAG VectorRAG 層次化摘要")
    assert len(info["rewritten_queries"]) >= 2


def test_rewrite_handles_pure_cjk() -> None:
    info = rewrite_query("知識圖譜推理")
    assert info["tokens"]


def test_rewrite_handles_empty() -> None:
    info = rewrite_query("")
    assert info["tokens"] == []
    assert info["rewritten_queries"] == [""]


def test_rewrite_loads_aliases_from_config() -> None:
    cfg = RagConfig(
        retrieval=RetrievalConfig(),
        query_rewrite_aliases={"CustomTerm": ["custom alias value"]},
    )
    info = rewrite_query("CustomTerm", cfg=cfg)
    assert "custom alias value" in info["alias_expansions"]


# ---- no-answer behavior (synthetic) ----


@pytest.fixture()
def sample_notes_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "sample_data" / "notes"


def test_no_answer_threshold_triggers_on_low_score(
    tmp_path: Path, sample_notes_dir: Path
) -> None:
    """When the top score is below no_answer_threshold, results are empty."""
    from rdos.config import (
        ChunkingConfig,
        EmbeddingConfig,
        EmbeddingRuntimeConfig,
        ModelsConfig,
        PrivacyPolicyConfig,
        PrivacyRule,
        ProfileConfig,
        RdosConfig,
        StorageConfig,
    )
    from rdos.rag.embedding import build_embedding_provider
    from rdos.rag.hybrid_search import RetrievalFilters
    from rdos.rag.indexer import index_directory
    from rdos.rag.retriever import HybridRetriever
    from rdos.rag.storage_sqlite import SqliteMetadataStore
    from rdos.rag.vector_store import LanceVectorStore

    cfg = RdosConfig(
        models=ModelsConfig(
            profiles={"local_fast": ProfileConfig(provider="local", model="stub")},
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
        ),
        rag=RagConfig(
            chunking=ChunkingConfig(target_min_tokens=30, target_max_tokens=120),
            storage=StorageConfig(
                sqlite_path=str(tmp_path / "rdos.db"),
                lancedb_path=str(tmp_path / "lancedb"),
            ),
            embedding=EmbeddingRuntimeConfig(dim=64),
            retrieval=RetrievalConfig(
                top_k=3,
                no_answer_threshold=0.5,  # higher than any fake-embedding RRF score
                enable_query_rewrite=False,
            ),
        ),
    )

    index_directory(sample_notes_dir, config=cfg)
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    emb = build_embedding_provider("fake", dim=64)
    retriever = HybridRetriever(sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg)

    result = retriever.search("anything", top_k=3, filters=RetrievalFilters())
    assert result.no_answer_triggered is True
    assert result.chunks == []
    store.close()


# ---- benchmark smoke ----


def test_benchmark_returns_metrics_dict_structure(sample_notes_dir: Path, tmp_path: Path) -> None:
    """Benchmark should return a metrics dict even on a tiny corpus."""
    from rdos.config import (
        ChunkingConfig,
        EmbeddingConfig,
        EmbeddingRuntimeConfig,
        ModelsConfig,
        PrivacyPolicyConfig,
        PrivacyRule,
        ProfileConfig,
        RdosConfig,
        StorageConfig,
    )
    from rdos.eval.retrieval_benchmark import benchmark_retrieval
    from rdos.rag.indexer import index_directory

    cfg = RdosConfig(
        models=ModelsConfig(
            profiles={"local_fast": ProfileConfig(provider="local", model="stub")},
            embedding=EmbeddingConfig(provider="fake", dim=32),
        ),
        privacy_policy=PrivacyPolicyConfig(
            privacy_order=["public", "private_summary", "private_raw", "company_sensitive"],
            default_chunk_privacy="private_raw",
            default_query_privacy="private_raw",
            rules={
                lv: PrivacyRule(allow_external_model=False, requires_user_confirmation=False)
                for lv in ("public", "private_summary", "private_raw", "company_sensitive")
            },
        ),
        rag=RagConfig(
            chunking=ChunkingConfig(target_min_tokens=30, target_max_tokens=120),
            storage=StorageConfig(
                sqlite_path=str(tmp_path / "rdos.db"),
                lancedb_path=str(tmp_path / "lancedb"),
            ),
            embedding=EmbeddingRuntimeConfig(dim=32),
            retrieval=RetrievalConfig(top_k=3, enable_query_rewrite=False),
        ),
    )
    index_directory(sample_notes_dir, config=cfg)

    eval_set = tmp_path / "tiny.jsonl"
    eval_set.write_text(
        '{"id":"t1","question":"RAG filtering","expected_topics":["notes"],"expected_keywords":["rag"],"expected_files":[],"answer_type":"synthesis"}\n',
        encoding="utf-8",
    )

    out = benchmark_retrieval(cfg, eval_set=str(eval_set))
    assert "samples" in out
    assert "recall_at_5" in out
    assert "latency_p50_ms" in out
    assert out["samples"] == 1


def test_benchmark_cli_wired() -> None:
    from rdos.cli.benchmark import app

    assert app is not None
