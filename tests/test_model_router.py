"""Tests for ModelRouter."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.config import (
    EmbeddingConfig,
    ModelsConfig,
    ProfileConfig,
    load_config,
)
from rdos.llm.model_router import ModelRouter, RoutingInput
from rdos.schemas.privacy import PrivacyLevel


@pytest.fixture()
def models() -> ModelsConfig:
    return ModelsConfig(
        profiles={
            "local_fast": ProfileConfig(
                provider="local",
                model="qwythos-9b-q4",
                max_tokens=4096,
                temperature=0.3,
            ),
            "cloud_reasoning": ProfileConfig(
                provider="cloud",
                model="gpt-4o",
                max_tokens=8192,
                temperature=0.2,
            ),
            "code_specialist": ProfileConfig(
                provider="cloud",
                model="gpt-4o",
                max_tokens=8192,
                temperature=0.1,
            ),
        },
        task_defaults={
            "research_memory": "local_fast",
            "research_synthesis": "cloud_reasoning",
            "code_analysis": "code_specialist",
        },
        embedding=EmbeddingConfig(provider="fake", dim=64),
    )


def test_public_synthesis_picks_cloud(models: ModelsConfig) -> None:
    router = ModelRouter(models)
    decision = router.select(
        RoutingInput(
            task_type="research_synthesis",
            effective_privacy_level=PrivacyLevel.public,
        )
    )
    assert decision.selected_profile == "cloud_reasoning"
    assert decision.provider == "cloud"
    assert decision.allows_external_model is True
    assert decision.requires_user_confirmation is False


def test_private_raw_research_memory_is_local(models: ModelsConfig) -> None:
    router = ModelRouter(models)
    decision = router.select(
        RoutingInput(
            task_type="research_memory",
            effective_privacy_level=PrivacyLevel.private_raw,
        )
    )
    assert decision.selected_profile == "local_fast"
    assert decision.provider == "local"
    assert decision.allows_external_model is False


def test_company_sensitive_code_task_is_local_or_blocked(models: ModelsConfig) -> None:
    router = ModelRouter(models)
    decision = router.select(
        RoutingInput(
            task_type="code_analysis",
            effective_privacy_level=PrivacyLevel.company_sensitive,
        )
    )
    # code_specialist is cloud → router must force down to local_fast
    assert decision.selected_profile == "local_fast"
    assert decision.provider == "local"
    assert decision.allows_external_model is False


def test_private_summary_cloud_escalation_needs_confirmation(models: ModelsConfig) -> None:
    router = ModelRouter(models)
    decision = router.select(
        RoutingInput(
            task_type="research_synthesis",
            effective_privacy_level=PrivacyLevel.private_summary,
        )
    )
    # research_synthesis default is cloud_reasoning → escalation path
    assert decision.selected_profile == "cloud_reasoning"
    assert decision.provider == "cloud"
    assert decision.allows_external_model is True
    assert decision.requires_user_confirmation is True


def test_high_risk_private_raw_forced_local(models: ModelsConfig) -> None:
    router = ModelRouter(models)
    decision = router.select(
        RoutingInput(
            task_type="research_synthesis",
            effective_privacy_level=PrivacyLevel.private_raw,
            risk_level="high",
        )
    )
    assert decision.provider == "local"
    assert decision.allows_external_model is False


def test_decision_has_no_callable_model(models: ModelsConfig) -> None:
    router = ModelRouter(models)
    decision = router.select(
        RoutingInput(
            task_type="research_memory",
            effective_privacy_level=PrivacyLevel.public,
        )
    )
    # Decision must be pure data — no callable bound model fields
    dumped = decision.model_dump()
    for v in dumped.values():
        assert not callable(v)


def test_router_loads_from_real_configs(configs_dir: Path) -> None:
    cfg = load_config(configs_dir)
    router = ModelRouter(cfg.models)
    decision = router.select(
        RoutingInput(
            task_type="research_memory",
            effective_privacy_level=PrivacyLevel.private_raw,
        )
    )
    assert decision.provider == "local"


@pytest.fixture()
def configs_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "configs"
