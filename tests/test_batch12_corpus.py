"""Tests for Batch 12: real corpus ingestion."""

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
from rdos.rag.chunker import chunk_document
from rdos.rag.corpus_presets import CORPUS_PRESETS, get_preset, resolve_corpus_root
from rdos.rag.indexer import index_directory
from rdos.rag.markdown_parser import (
    derive_topic_from_path,
    parse_markdown_text,
)
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.schemas.privacy import PrivacyLevel

# ---- frontmatter gap handling ----


def test_title_falls_back_to_h1() -> None:
    text = "# My Real Title\n\nbody\n"
    meta, _ = parse_markdown_text(text, file_path="foo.md", source_collection="x")
    assert meta.title == "My Real Title"


def test_title_falls_back_to_filename_when_no_h1() -> None:
    meta, _ = parse_markdown_text("body only", file_path="foo-bar.md")
    assert meta.title == "foo-bar"


def test_date_extracted_from_filename_yymmdd() -> None:
    meta, _ = parse_markdown_text("body", file_path="260704 note.md")
    assert meta.date == "2026-07-04"


def test_privacy_default_applied_when_missing() -> None:
    meta, _ = parse_markdown_text(
        "body",
        file_path="x.md",
        privacy_default=PrivacyLevel.company_sensitive,
    )
    assert meta.privacy_level == PrivacyLevel.company_sensitive


def test_source_collection_and_topic_propagated(tmp_path: Path) -> None:
    root = tmp_path / "clawd-research"
    sub = root / "知識與檢索"
    sub.mkdir(parents=True)
    note = sub / "260704 rag.md"
    note.write_text("# RAG\nbody", encoding="utf-8")

    meta, _ = parse_markdown_text(
        note.read_text(encoding="utf-8"),
        file_path=str(note),
        source_collection="clawd-research",
        topic="知識與檢索",
    )
    assert meta.source_collection == "clawd-research"
    assert meta.topic == "知識與檢索"


def test_derive_topic_from_path(tmp_path: Path) -> None:
    root = tmp_path / "clawd-research"
    sub = root / "AI代理系統"
    sub.mkdir(parents=True)
    fp = sub / "note.md"
    fp.write_text("x", encoding="utf-8")
    assert derive_topic_from_path(fp, root=root) == "AI代理系統"


# ---- incremental index ----


def _make_cfg(tmp_path: Path) -> RdosConfig:
    return RdosConfig(
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
            chunking=ChunkingConfig(target_min_tokens=20, target_max_tokens=80),
            storage=StorageConfig(
                sqlite_path=str(tmp_path / "rdos.db"),
                lancedb_path=str(tmp_path / "lancedb"),
            ),
            embedding=EmbeddingRuntimeConfig(dim=32),
            retrieval=RetrievalConfig(),
        ),
    )


@pytest.fixture()
def synthetic_corpus(tmp_path: Path) -> Path:
    """Build a 2-topic mini corpus that mirrors clawd-research structure."""
    root = tmp_path / "clawd-research"
    (root / "知識與檢索").mkdir(parents=True)
    (root / "AI代理系統").mkdir(parents=True)
    (root / "知識與檢索" / "260701 rag.md").write_text(
        "---\ntitle: RAG Note\ntags: [rag]\nprivacy_level: private_raw\n---\n\n# RAG\nhybrid retrieval body",
        encoding="utf-8",
    )
    (root / "知識與檢索" / "260702 graphrag.md").write_text(
        "# GraphRAG\nlayered summary body",
        encoding="utf-8",
    )
    (root / "AI代理系統" / "260703 agent.md").write_text(
        "---\ntitle: Agent Trace\nprivacy_level: private_summary\n---\n\n# AgentTrace\nflight recorder",
        encoding="utf-8",
    )
    return root


def test_incremental_index_skips_unchanged(synthetic_corpus: Path, tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    first = index_directory(synthetic_corpus, config=cfg, source_collection="clawd-research")
    assert first.documents_created >= 3
    assert first.chunks_inserted > 0

    second = index_directory(synthetic_corpus, config=cfg, source_collection="clawd-research")
    assert second.documents_unchanged >= 3
    assert second.documents_created == 0
    assert second.chunks_inserted == 0


def test_incremental_index_reindexes_modified(synthetic_corpus: Path, tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    index_directory(synthetic_corpus, config=cfg, source_collection="clawd-research")

    target = synthetic_corpus / "知識與檢索" / "260701 rag.md"
    target.write_text(
        "---\ntitle: RAG Note v2\ntags: [rag]\nprivacy_level: private_raw\n---\n\n# RAG v2\nnew content",
        encoding="utf-8",
    )
    second = index_directory(synthetic_corpus, config=cfg, source_collection="clawd-research")
    assert second.documents_updated >= 1


def test_missing_file_marked_stale(synthetic_corpus: Path, tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    index_directory(synthetic_corpus, config=cfg, source_collection="clawd-research")

    (synthetic_corpus / "知識與檢索" / "260702 graphrag.md").unlink()
    second = index_directory(synthetic_corpus, config=cfg, source_collection="clawd-research")
    assert second.documents_stale >= 1


def test_source_collection_metadata_propagated_to_chunks(
    synthetic_corpus: Path, tmp_path: Path
) -> None:
    cfg = _make_cfg(tmp_path)
    stats = index_directory(synthetic_corpus, config=cfg, source_collection="clawd-research")
    assert stats.source_collection == "clawd-research"

    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    docs = store.all_documents()
    assert all(d.source_collection == "clawd-research" for d in docs if d.source_collection)
    store.close()


def test_index_report_written(synthetic_corpus: Path, tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    report_path = tmp_path / "reports" / "index_report.md"
    index_directory(
        synthetic_corpus,
        config=cfg,
        source_collection="clawd-research",
        report_path=report_path,
    )
    assert report_path.exists()
    body = report_path.read_text(encoding="utf-8")
    assert "documents created" in body.lower() or "documents indexed" in body.lower()
    assert "clawd-research" in body
    assert "topic distribution" in body.lower()


def test_topic_distribution_in_stats(synthetic_corpus: Path, tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    stats = index_directory(synthetic_corpus, config=cfg, source_collection="clawd-research")
    topics = stats.topic_distribution
    assert topics.get("知識與檢索", 0) >= 2
    assert topics.get("AI代理系統", 0) >= 1


# ---- corpus presets ----


def test_preset_known_scopes() -> None:
    scopes = CORPUS_PRESETS["research-notes"]
    assert set(scopes) >= {"rag", "agent", "eval", "security", "devtools", "all"}


def test_preset_rag_folder() -> None:
    preset = get_preset("research-notes", "rag")
    assert preset.folders == ("知識與檢索",)


def test_legacy_clawd_research_preset_alias_still_supported() -> None:
    preset = get_preset("clawd-research", "rag")
    assert preset.folders == ("知識與檢索",)


def test_preset_unknown_scope_raises() -> None:
    with pytest.raises(ValueError):
        get_preset("research-notes", "bogus")


def test_resolve_corpus_root_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RDOS_CORPUS_RESEARCH_NOTES_ROOT", str(tmp_path))
    assert resolve_corpus_root("research-notes") == str(tmp_path)


def test_resolve_corpus_root_unknown_raises() -> None:
    with pytest.raises(ValueError):
        resolve_corpus_root("nonsense")


# ---- smoke: chunker doesn't drop new fields ----


def test_chunk_carries_corpus_metadata(synthetic_corpus: Path) -> None:
    note = synthetic_corpus / "知識與檢索" / "260701 rag.md"
    meta, body = parse_markdown_text(
        note.read_text(encoding="utf-8"),
        file_path=str(note),
        source_collection="clawd-research",
        topic="知識與檢索",
    )
    chunks = chunk_document(meta, body)
    assert chunks
    for c in chunks:
        assert c.source_collection == "clawd-research"
        assert c.topic == "知識與檢索"
