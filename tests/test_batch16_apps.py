"""Tests for Batch 16: real research apps."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.apps.digest import run_digest
from rdos.apps.synthesize import run_synthesis
from rdos.apps.topic import run_topic_explorer
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
from rdos.rag.indexer import index_directory


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
            retrieval=RetrievalConfig(top_k=3, enable_query_rewrite=False),
        ),
    )
    index_directory(sample_notes_dir, config=cfg, source_collection="test")
    return cfg


def test_digest_produces_markdown(indexed_config: RdosConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Re-route output to tmp_path
    monkeypatch.chdir(tmp_path)
    out, md = run_digest(cfg=indexed_config, since="2026-07-01", source_collection="test")
    assert Path(md).exists()
    assert out.notes
    assert Path(md).read_text(encoding="utf-8").startswith("# Daily R&D Digest")


def test_topic_explorer_runs(indexed_config: RdosConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    out, md = run_topic_explorer(cfg=indexed_config, topic="RAG")
    assert Path(md).exists()
    # Hot keywords populated
    assert isinstance(out.hot_keywords, list)


def test_synthesize_runs_with_stub(indexed_config: RdosConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    out, md = run_synthesis(cfg=indexed_config, question="RAG filtering 是什麼？")
    assert Path(md).exists()
    # Citation coverage reported
    assert 0.0 <= out.citation_coverage <= 1.0
    # Some claims produced
    assert isinstance(out.claims, list)


def test_synthesize_citation_validation_in_report(indexed_config: RdosConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    out, md = run_synthesis(cfg=indexed_config, question="RAG filtering 是什麼？")
    body = Path(md).read_text(encoding="utf-8")
    assert "citation_coverage" in body
    assert "all_valid" in body


def test_apps_cli_wired() -> None:
    from rdos.cli.research_apps import app

    assert app is not None


@pytest.fixture()
def sample_notes_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "sample_data" / "notes"
