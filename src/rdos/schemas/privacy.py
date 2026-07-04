"""Privacy-related schemas."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PrivacyLevel(str, Enum):
    """Privacy classification, low → high."""

    public = "public"
    private_summary = "private_summary"
    private_raw = "private_raw"
    company_sensitive = "company_sensitive"


PRIVACY_ORDER: list[PrivacyLevel] = [
    PrivacyLevel.public,
    PrivacyLevel.private_summary,
    PrivacyLevel.private_raw,
    PrivacyLevel.company_sensitive,
]

# Convenience numeric ordering for `max()`
_PRIVACY_RANK: dict[PrivacyLevel, int] = {level: i for i, level in enumerate(PRIVACY_ORDER)}


def privacy_max(levels: list[PrivacyLevel]) -> PrivacyLevel:
    """Return the strictest (highest-rank) privacy level in the list.

    Empty list → public (lowest). Unknown / None treated as default.
    """
    if not levels:
        return PrivacyLevel.public
    resolved = [lvl for lvl in levels if lvl is not None]
    if not resolved:
        return PrivacyLevel.public
    return max(resolved, key=lambda lvl: _PRIVACY_RANK[lvl])


def privacy_rank(level: PrivacyLevel) -> int:
    """Numeric rank for comparison. Higher = stricter."""
    return _PRIVACY_RANK[level]


class PrivacyDecision(BaseModel):
    """Result of the PrivacyRouter.

    Captures each input source plus the final effective privacy level.
    """

    user_query_privacy: PrivacyLevel
    retrieved_chunk_privacies: list[PrivacyLevel] = Field(default_factory=list)
    tool_result_privacies: list[PrivacyLevel] = Field(default_factory=list)
    memory_context_privacies: list[PrivacyLevel] = Field(default_factory=list)
    trace_context_privacies: list[PrivacyLevel] = Field(default_factory=list)

    effective_privacy_level: PrivacyLevel

    allows_external_model: bool
    requires_user_confirmation: bool
    reason: str = ""
