"""Tests for the config loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.config import RdosConfig, get_config, load_config


@pytest.fixture()
def configs_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "configs"


def test_load_config_returns_rdos_config(configs_dir: Path) -> None:
    cfg = load_config(configs_dir)
    assert isinstance(cfg, RdosConfig)


def test_load_config_has_models(configs_dir: Path) -> None:
    cfg = load_config(configs_dir)
    assert "local_fast" in cfg.models.profiles
    assert cfg.models.profiles["local_fast"].provider == "local"
    assert "cloud_reasoning" in cfg.models.profiles


def test_load_config_has_privacy_policy(configs_dir: Path) -> None:
    cfg = load_config(configs_dir)
    assert cfg.privacy_policy.privacy_order == [
        "public",
        "private_summary",
        "private_raw",
        "company_sensitive",
    ]
    assert cfg.privacy_policy.rules["private_raw"].allow_external_model is False
    assert cfg.privacy_policy.rules["company_sensitive"].allow_external_model is False
    assert cfg.privacy_policy.rules["private_summary"].requires_user_confirmation is True


def test_load_config_has_rag(configs_dir: Path) -> None:
    cfg = load_config(configs_dir)
    assert cfg.rag.chunking.target_min_tokens >= 100
    assert cfg.rag.chunking.target_max_tokens > cfg.rag.chunking.target_min_tokens
    assert 0 <= cfg.rag.retrieval.semantic_weight <= 1


def test_load_config_has_tool_policy(configs_dir: Path) -> None:
    cfg = load_config(configs_dir)
    assert "web_search" in cfg.tool_policy.tools
    assert "company_sensitive" in cfg.tool_policy.tools["web_search"].blocked_privacy


def test_env_substitution(monkeypatch: pytest.MonkeyPatch, configs_dir: Path) -> None:
    monkeypatch.setenv("RDOS_LOCAL_CHAT_BASE_URL", "http://test:9999")
    cfg = load_config(configs_dir)
    assert cfg.models.profiles["local_fast"].base_url == "http://test:9999"


def test_get_config_is_cached() -> None:
    get_config.cache_clear()
    a = get_config()
    b = get_config()
    assert a is b
    get_config.cache_clear()
