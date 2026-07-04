"""Smoke tests for the Batch 0 skeleton."""

from __future__ import annotations

import numpy as np

from rdos import __version__
from rdos.llm.provider import LLMMessage, StubLLMAdapter
from rdos.rag.embedding import FakeEmbeddingProvider, build_embedding_provider


def test_version_is_pep440() -> None:
    assert __version__.count(".") >= 1, "version should look like X.Y.Z"
    parts = __version__.split(".")
    assert all(p.replace("0", "").isalnum() or p.isdigit() for p in parts)


def test_fake_embedding_is_deterministic() -> None:
    emb = FakeEmbeddingProvider(dim=64)
    a = emb.embed_one("hello world")
    b = emb.embed_one("hello world")
    assert a == b
    assert len(a) == 64
    # Unit-norm
    np.testing.assert_allclose(np.linalg.norm(a), 1.0, atol=1e-5)


def test_fake_embedding_differs_for_different_text() -> None:
    emb = FakeEmbeddingProvider(dim=64)
    a = emb.embed_one("apple")
    b = emb.embed_one("orange")
    assert a != b


def test_fake_embedding_batch_matches_single() -> None:
    emb = FakeEmbeddingProvider(dim=32)
    texts = ["alpha", "beta", "gamma"]
    batch = emb.embed(texts)
    singles = [emb.embed_one(t) for t in texts]
    assert batch == singles


def test_build_embedding_provider_fake() -> None:
    emb = build_embedding_provider("fake", dim=16)
    assert emb.dim == 16
    assert len(emb.embed_one("x")) == 16


def test_build_embedding_provider_unknown_raises() -> None:
    try:
        build_embedding_provider("nope")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_stub_llm_adapter_basic() -> None:
    adapter = StubLLMAdapter(model="stub-1", provider="stub")
    assert adapter.model_name == "stub-1"
    assert adapter.provider_name == "stub"
    resp = adapter.generate([LLMMessage(role="user", content="ping")])
    assert resp.model == "stub-1"
    assert "ping" in resp.text


def test_cli_app_object_exists() -> None:
    from rdos.cli import app

    assert app is not None
