"""PermissionGate — privacy-aware tool permission decisions."""

from __future__ import annotations

from dataclasses import dataclass

from rdos.config import ToolPolicyConfig
from rdos.schemas.privacy import PrivacyLevel


@dataclass
class PermissionDecision:
    tool_name: str
    permission_level: str
    allowed: bool
    requires_approval: bool
    reason: str


class PermissionGate:
    """Decide tool eligibility based on policy + effective privacy level."""

    def __init__(self, policy: ToolPolicyConfig) -> None:
        self.policy = policy
        self.default = policy.default_policy

    def evaluate(
        self,
        tool_name: str,
        effective_privacy: PrivacyLevel,
    ) -> PermissionDecision:
        rule = self.policy.tools.get(tool_name)
        if rule is None:
            return PermissionDecision(
                tool_name=tool_name,
                permission_level="unknown",
                allowed=(self.default == "allow"),
                requires_approval=False,
                reason=f"tool not registered; default_policy={self.default}",
            )

        priv = effective_privacy.value

        if priv in rule.blocked_privacy:
            return PermissionDecision(
                tool_name=tool_name,
                permission_level=rule.description or "blocked",
                allowed=False,
                requires_approval=False,
                reason=f"blocked for privacy level {priv}",
            )

        if priv in rule.requires_confirmation:
            return PermissionDecision(
                tool_name=tool_name,
                permission_level=rule.description or "confirm",
                allowed=False,
                requires_approval=True,
                reason=f"requires confirmation for privacy level {priv}",
            )

        if priv in rule.allowed_privacy:
            return PermissionDecision(
                tool_name=tool_name,
                permission_level=rule.description or "allowed",
                allowed=True,
                requires_approval=False,
                reason=f"allowed for privacy level {priv}",
            )

        # Default deny when nothing matches.
        return PermissionDecision(
            tool_name=tool_name,
            permission_level=rule.description or "deny",
            allowed=(self.default == "allow"),
            requires_approval=False,
            reason=f"privacy level {priv} not explicitly allowed (default={self.default})",
        )
