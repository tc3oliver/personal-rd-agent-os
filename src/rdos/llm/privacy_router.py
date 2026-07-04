"""Privacy router — computes effective privacy across all input sources."""

from __future__ import annotations

from dataclasses import dataclass

from rdos.config import PrivacyPolicyConfig, PrivacyRule
from rdos.schemas.document import DocumentChunk
from rdos.schemas.privacy import (
    PrivacyDecision,
    PrivacyLevel,
    privacy_max,
    privacy_rank,
)


@dataclass
class PrivacyInput:
    user_query: str
    user_query_privacy: PrivacyLevel
    retrieved_chunks: list[DocumentChunk] | None = None
    tool_result_privacies: list[PrivacyLevel] | None = None
    memory_context_privacies: list[PrivacyLevel] | None = None
    trace_context_privacies: list[PrivacyLevel] | None = None


class PrivacyRouter:
    """Computes the strictest privacy level across all input sources.

    effective = max(
        user_query_privacy,
        retrieved_chunks.privacy_levels,
        tool_result_privacies,
        memory_context_privacies,
        trace_context_privacies,
    )

    public < private_summary < private_raw < company_sensitive
    """

    def __init__(self, policy: PrivacyPolicyConfig) -> None:
        self.policy = policy
        self.rules: dict[str, PrivacyRule] = policy.rules

    def assess_query(self, query: str, default: PrivacyLevel | None = None) -> PrivacyLevel:
        """Heuristic query privacy classification based on policy hints.

        Real classification belongs to a small classifier; this is a keyword
        fallback that uses policy.query_privacy_hints.
        """
        if default is None:
            default = PrivacyLevel(self.policy.default_query_privacy)
        text = query.lower()
        # Check from strictest to loosest so strictest wins
        for level in (
            PrivacyLevel.company_sensitive,
            PrivacyLevel.private_raw,
            PrivacyLevel.private_summary,
            PrivacyLevel.public,
        ):
            hints = self.policy.query_privacy_hints.get(level.value, [])
            for hint in hints:
                if hint and hint.lower() in text:
                    return level
        return default

    def calculate_effective_privacy(self, inp: PrivacyInput) -> PrivacyDecision:
        chunk_levels: list[PrivacyLevel] = (
            [c.privacy_level for c in inp.retrieved_chunks]
            if inp.retrieved_chunks
            else []
        )
        tool_levels = inp.tool_result_privacies or []
        memory_levels = inp.memory_context_privacies or []
        trace_levels = inp.trace_context_privacies or []

        all_levels = (
            [inp.user_query_privacy]
            + chunk_levels
            + tool_levels
            + memory_levels
            + trace_levels
        )
        effective = privacy_max(all_levels)
        rule = self._rule_for(effective)

        # Sanity: strictest levels must block external
        if effective in (PrivacyLevel.private_raw, PrivacyLevel.company_sensitive):
            allows_external = False
            requires_confirmation = False
        elif effective == PrivacyLevel.private_summary:
            allows_external = rule.allow_external_model  # typically True
            requires_confirmation = True  # escalation needs confirmation
        else:  # public
            allows_external = rule.allow_external_model
            requires_confirmation = rule.requires_user_confirmation

        return PrivacyDecision(
            user_query_privacy=inp.user_query_privacy,
            retrieved_chunk_privacies=chunk_levels,
            tool_result_privacies=tool_levels,
            memory_context_privacies=memory_levels,
            trace_context_privacies=trace_levels,
            effective_privacy_level=effective,
            allows_external_model=allows_external,
            requires_user_confirmation=requires_confirmation,
            reason=self._build_reason(inp, effective),
        )

    def _rule_for(self, level: PrivacyLevel) -> PrivacyRule:
        rule = self.rules.get(level.value)
        if rule is None:
            return PrivacyRule(
                allow_external_model=False,
                requires_user_confirmation=False,
            )
        return rule

    def _build_reason(self, inp: PrivacyInput, effective: PrivacyLevel) -> str:
        parts: list[str] = [f"effective={effective.value}"]
        parts.append(f"query={inp.user_query_privacy.value}")
        if inp.retrieved_chunks:
            chunk_strictest = privacy_max([c.privacy_level for c in inp.retrieved_chunks])
            parts.append(f"chunks_strictest={chunk_strictest.value}")
        parts.append(f"rank={privacy_rank(effective)}")
        return " ".join(parts)
