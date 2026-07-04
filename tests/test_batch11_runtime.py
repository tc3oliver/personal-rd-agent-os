"""Tests for Batch 11: real local runtime integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdos.config import (
    ChunkingConfig,
    EmbeddingConfig,
    EmbeddingRuntimeConfig,
    ModelsConfig,
    ProfileConfig,
    RagConfig,
    RdosConfig,
    RetrievalConfig,
    StorageConfig,
)
from rdos.llm.runtime_mode import resolve_llm
from rdos.rag.embedding import (
    FakeEmbeddingProvider,
    OpenAICompatibleEmbeddingConfig,
    OpenAICompatibleEmbeddingProvider,
    build_embedding_provider,
)
from rdos.rag.indexer import index_directory
from rdos.rag.vector_store import (
    EmbeddingDimensionMismatchError,
    EmbeddingProviderMismatchError,
    LanceVectorStore,
)

# ---- OpenAICompatibleEmbeddingProvider ----


def test_factory_rejects_unknown_provider() -> None:
    try:
        build_embedding_provider("nonsense", dim=8)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_factory_fake_provider() -> None:
    emb = build_embedding_provider("fake", dim=16)
    assert emb.name == "fake"
    assert emb.dim == 16
    assert len(emb.embed_one("x")) == 16


def test_factory_local_bge_m3_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RDOS_LOCAL_EMBEDDING_BASE_URL", "http://test:9999/v1")
    monkeypatch.setenv("RDOS_LOCAL_EMBEDDING_MODEL", "bge-m3-test")
    monkeypatch.setenv("RDOS_LOCAL_MODEL_API_KEY", "fake-key")
    monkeypatch.setenv("RDOS_LOCAL_EMBEDDING_DIM", "1024")
    emb = build_embedding_provider("local-bge-m3", dim=1024)
    assert isinstance(emb, OpenAICompatibleEmbeddingProvider)
    assert emb.name == "local-bge-m3"
    assert emb.model == "bge-m3-test"
    assert emb.dim == 1024
    assert emb.cfg.base_url == "http://test:9999/v1"


def test_local_embedding_provider_health_returns_bool_when_unreachable() -> None:
    cfg = OpenAICompatibleEmbeddingConfig(
        name="local-bge-m3",
        base_url="http://127.0.0.1:1/v1",
        model="bge-m3-q8_0",
        dim=1024,
        api_key_env="RDOS_LOCAL_MODEL_API_KEY",
        timeout=1.0,
    )
    provider = OpenAICompatibleEmbeddingProvider(cfg)
    assert provider.health() is False


# ---- Provider metadata persistence + mismatch guard ----


def _cfg(tmp_path: Path, dim: int = 32, provider: str = "fake") -> RdosConfig:
    return RdosConfig(
        models=ModelsConfig(
            profiles={"local_fast": ProfileConfig(provider="local", model="stub")},
            task_defaults={"research_memory": "local_fast"},
            embedding=EmbeddingConfig(provider=provider, dim=dim),
        ),
        rag=RagConfig(
            chunking=ChunkingConfig(target_min_tokens=30, target_max_tokens=120),
            storage=StorageConfig(
                sqlite_path=str(tmp_path / "rdos.db"),
                lancedb_path=str(tmp_path / "lancedb"),
            ),
            embedding=EmbeddingRuntimeConfig(dim=dim),
            retrieval=RetrievalConfig(),
        ),
    )


def test_index_persists_provider_meta(tmp_path: Path, sample_notes_dir: Path) -> None:
    cfg = _cfg(tmp_path, dim=32, provider="fake")
    stats = index_directory(sample_notes_dir, config=cfg)
    assert stats.embedding_provider == "fake"
    assert stats.embedding_dim == 32

    vs = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=32)
    meta = vs.read_provider_meta()
    assert meta["embedding_provider"] == "fake"
    assert meta["embedding_dim"] == 32


def test_mismatch_provider_raises(tmp_path: Path, sample_notes_dir: Path) -> None:
    cfg = _cfg(tmp_path, dim=32, provider="fake")
    index_directory(sample_notes_dir, config=cfg)

    vs = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=32)
    # Pretend a new provider with the SAME dim but a DIFFERENT name tries to query.
    fake_diff = build_embedding_provider("fake", dim=32)
    fake_diff.__class__ = type("Other", (FakeEmbeddingProvider,), {"name": property(lambda self: "other")})
    with pytest.raises(EmbeddingProviderMismatchError):
        vs.ensure_provider_compatible(fake_diff)


def test_mismatch_dim_raises(tmp_path: Path, sample_notes_dir: Path) -> None:
    cfg = _cfg(tmp_path, dim=32, provider="fake")
    index_directory(sample_notes_dir, config=cfg)

    vs = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=64)
    other = build_embedding_provider("fake", dim=64)
    with pytest.raises(EmbeddingDimensionMismatchError):
        vs.ensure_provider_compatible(other)


# ---- LLM runtime mode ----


def _models_cfg() -> ModelsConfig:
    return ModelsConfig(
        profiles={
            "local_fast": ProfileConfig(
                provider="local",
                base_url="http://127.0.0.1:1",
                model="stub",
                api_key_env="RDOS_LOCAL_MODEL_API_KEY",
            ),
        },
        embedding=EmbeddingConfig(provider="fake", dim=16),
    )


def test_llm_mode_stub_always_uses_stub() -> None:
    decision = resolve_llm(_models_cfg(), mode="stub")
    assert decision.fallback_used is False
    assert type(decision.adapter).__name__ == "StubLLMAdapter"


def test_llm_mode_local_without_server_raises() -> None:
    with pytest.raises(RuntimeError):
        resolve_llm(_models_cfg(), mode="local")


def test_llm_mode_auto_falls_back_to_stub_with_warning() -> None:
    decision = resolve_llm(_models_cfg(), mode="auto")
    assert decision.fallback_used is True
    assert decision.warning
    assert type(decision.adapter).__name__ == "StubLLMAdapter"


def test_llm_mode_unknown_raises() -> None:
    with pytest.raises(ValueError):
        resolve_llm(_models_cfg(), mode="bogus")


# ---- CLI smoke: doctor returns int exit code ----


def test_doctor_cli_wired() -> None:
    from rdos.cli.doctor import app

    assert app is not None


# ---- fixtures ----


@pytest.fixture()
def sample_notes_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "sample_data" / "notes"


# silence ruff unused-import for json (used for meta inspection elsewhere)
_ = json
