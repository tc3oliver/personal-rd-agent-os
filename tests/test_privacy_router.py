"""Tests for PrivacyRouter."""

from __future__ import annotations

import pytest

from rdos.config import PrivacyPolicyConfig, PrivacyRule
from rdos.llm.privacy_router import PrivacyInput, PrivacyRouter
from rdos.schemas.document import DocumentChunk
from rdos.schemas.privacy import PrivacyLevel


@pytest.fixture()
def policy() -> PrivacyPolicyConfig:
    return PrivacyPolicyConfig(
        privacy_order=["public", "private_summary", "private_raw", "company_sensitive"],
        default_chunk_privacy="private_raw",
        default_query_privacy="private_raw",
        rules={
            "public": PrivacyRule(allow_external_model=True, requires_user_confirmation=False),
            "private_summary": PrivacyRule(
                allow_external_model=True, requires_user_confirmation=True
            ),
            "private_raw": PrivacyRule(
                allow_external_model=False, requires_user_confirmation=False
            ),
            "company_sensitive": PrivacyRule(
                allow_external_model=False, requires_user_confirmation=False
            ),
        },
        query_privacy_hints={
            "public": ["definition", "example"],
            "private_summary": ["my notes"],
            "private_raw": ["my journal"],
            "company_sensitive": ["internal", "confidential", "salary", "roadmap"],
        },
    )


def test_assess_query_keyword_classifier(policy: PrivacyPolicyConfig) -> None:
    router = PrivacyRouter(policy)
    assert router.assess_query("roadmap draft") == PrivacyLevel.company_sensitive
    assert router.assess_query("my journal today") == PrivacyLevel.private_raw
    assert router.assess_query("my notes draft") == PrivacyLevel.private_summary
    assert router.assess_query("definition of RAG") == PrivacyLevel.public


def test_assess_query_unknown_falls_to_default(policy: PrivacyPolicyConfig) -> None:
    router = PrivacyRouter(policy)
    assert router.assess_query("random query") == PrivacyLevel.private_raw


def _chunk(level: PrivacyLevel) -> DocumentChunk:
    return DocumentChunk(
        doc_id="d",
        file_path="x",
        title="t",
        heading_path=[],
        chunk_id="c",
        chunk_text="x",
        token_count=1,
        content_hash="h",
        chunk_hash="h",
        privacy_level=level,
    )


def test_effective_privacy_takes_strictest_chunk(policy: PrivacyPolicyConfig) -> None:
    router = PrivacyRouter(policy)
    pd = router.calculate_effective_privacy(
        PrivacyInput(
            user_query="public query",
            user_query_privacy=PrivacyLevel.public,
            retrieved_chunks=[
                _chunk(PrivacyLevel.public),
                _chunk(PrivacyLevel.company_sensitive),
            ],
        )
    )
    assert pd.effective_privacy_level == PrivacyLevel.company_sensitive
    assert pd.allows_external_model is False


def test_private_raw_blocks_external(policy: PrivacyPolicyConfig) -> None:
    router = PrivacyRouter(policy)
    pd = router.calculate_effective_privacy(
        PrivacyInput(
            user_query="private query",
            user_query_privacy=PrivacyLevel.private_raw,
        )
    )
    assert pd.effective_privacy_level == PrivacyLevel.private_raw
    assert pd.allows_external_model is False
    assert pd.requires_user_confirmation is False


def test_private_summary_cloud_needs_confirmation(policy: PrivacyPolicyConfig) -> None:
    router = PrivacyRouter(policy)
    pd = router.calculate_effective_privacy(
        PrivacyInput(
            user_query="my notes draft",
            user_query_privacy=PrivacyLevel.private_summary,
        )
    )
    assert pd.effective_privacy_level == PrivacyLevel.private_summary
    assert pd.allows_external_model is True
    assert pd.requires_user_confirmation is True


def test_public_no_confirmation(policy: PrivacyPolicyConfig) -> None:
    router = PrivacyRouter(policy)
    pd = router.calculate_effective_privacy(
        PrivacyInput(
            user_query="definition of RAG",
            user_query_privacy=PrivacyLevel.public,
        )
    )
    assert pd.effective_privacy_level == PrivacyLevel.public
    assert pd.allows_external_model is True
    assert pd.requires_user_confirmation is False


def test_tool_result_can_escalate_privacy(policy: PrivacyPolicyConfig) -> None:
    router = PrivacyRouter(policy)
    pd = router.calculate_effective_privacy(
        PrivacyInput(
            user_query="public query",
            user_query_privacy=PrivacyLevel.public,
            tool_result_privacies=[PrivacyLevel.company_sensitive],
        )
    )
    assert pd.effective_privacy_level == PrivacyLevel.company_sensitive
