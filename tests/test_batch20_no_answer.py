"""Tests for Batch 20: no-answer calibration."""

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
from rdos.eval.no_answer_calibrate import calibrate_thresholds
from rdos.eval.no_answer_eval import evaluate_no_answer
from rdos.eval.report import RELEASE_GATE
from rdos.rag.embedding import build_embedding_provider
from rdos.rag.hybrid_search import RetrievalFilters
from rdos.rag.indexer import index_directory
from rdos.rag.retriever import HybridRetriever
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore


@pytest.fixture()
def indexed_config(tmp_path: Path, sample_notes_dir: Path) -> RdosConfig:
    cfg = RdosConfig(
        models=ModelsConfig(
            profiles={"local_fast": ProfileConfig(provider="local", model="stub")},
            task_defaults={"research_memory": "local_fast"},
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
            retrieval=RetrievalConfig(top_k=3, enable_query_rewrite=False, no_answer_threshold=0.5),
        ),
    )
    index_directory(sample_notes_dir, config=cfg)
    return cfg


def test_no_answer_triggers_when_threshold_high(indexed_config: RdosConfig) -> None:
    cfg = indexed_config
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=32)
    emb = build_embedding_provider("fake", dim=32)
    retriever = HybridRetriever(sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg)

    result = retriever.search("anything", top_k=3, filters=RetrievalFilters())
    assert result.no_answer_triggered is True
    assert result.no_answer_reason
    assert "threshold" in result.no_answer_reason
    store.close()


def test_no_answer_disabled_when_threshold_zero(tmp_path: Path, sample_notes_dir: Path) -> None:
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
            retrieval=RetrievalConfig(top_k=3, enable_query_rewrite=False, no_answer_threshold=0.0),
        ),
    )
    index_directory(sample_notes_dir, config=cfg)
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=32)
    emb = build_embedding_provider("fake", dim=32)
    retriever = HybridRetriever(sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg)
    result = retriever.search("RAG filtering", top_k=3, filters=RetrievalFilters())
    assert result.no_answer_triggered is False
    assert result.chunks
    store.close()


def test_no_answer_evaluator_runs(indexed_config: RdosConfig, tmp_path: Path) -> None:
    na_set = tmp_path / "na.jsonl"
    na_set.write_text(
        '{"id":"na1","question":"ZZZZZ nonexistent","answer_type":"no_answer"}\n'
        '{"id":"na2","question":"YYYYY fake","answer_type":"no_answer"}\n',
        encoding="utf-8",
    )
    real_set = tmp_path / "real.jsonl"
    real_set.write_text(
        '{"id":"r1","question":"RAG filtering","expected_topics":["notes"],'
        '"expected_keywords":[],"expected_files":[],"answer_type":"synthesis"}\n',
        encoding="utf-8",
    )
    out = evaluate_no_answer(
        indexed_config, eval_set=na_set, real_eval_set=real_set
    )
    assert "no_answer_accuracy" in out
    assert "false_no_answer_rate" in out
    assert 0.0 <= out["no_answer_accuracy"] <= 1.0


def test_calibrate_returns_threshold(indexed_config: RdosConfig, tmp_path: Path) -> None:
    na_set = tmp_path / "na.jsonl"
    na_set.write_text(
        '{"id":"na1","question":"ZZZZZ nonexistent","answer_type":"no_answer"}\n',
        encoding="utf-8",
    )
    real_set = tmp_path / "real.jsonl"
    real_set.write_text(
        '{"id":"r1","question":"RAG filtering","expected_topics":["notes"],'
        '"expected_keywords":[],"expected_files":[],"answer_type":"synthesis"}\n',
        encoding="utf-8",
    )
    out = calibrate_thresholds(
        indexed_config, real_eval_set=real_set, no_answer_eval_set=na_set
    )
    assert "recommended_threshold" in out
    assert out["real_samples"] >= 0


def test_release_gate_has_no_answer_metrics() -> None:
    from rdos.eval.report import NO_ANSWER_GATE

    assert "no_answer_accuracy" in NO_ANSWER_GATE
    assert "false_no_answer_rate" in NO_ANSWER_GATE
    op, threshold = NO_ANSWER_GATE["no_answer_accuracy"]
    assert op == "gte" and threshold == 0.90
    op2, threshold2 = NO_ANSWER_GATE["false_no_answer_rate"]
    assert op2 == "lte" and threshold2 == 0.05


def test_release_gate_unchanged_for_foundation() -> None:
    """Foundation regression gate stays at 8 metrics (no-answer is separate)."""
    assert len(RELEASE_GATE) == 8
    assert "no_answer_accuracy" not in RELEASE_GATE


@pytest.fixture()
def sample_notes_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "sample_data" / "notes"
