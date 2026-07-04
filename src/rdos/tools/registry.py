"""ToolRegistry — discoverable safe tools for the agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from rdos.config import ToolPolicyConfig
from rdos.tools.capability_boundary import BoundaryResult, CapabilityBoundary
from rdos.tools.permission_gate import PermissionDecision, PermissionGate


class Tool(Protocol):
    name: str
    description: str

    def run(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass
class ToolInvocation:
    decision: PermissionDecision
    boundary: BoundaryResult | None
    output: dict[str, Any] | None


class ToolRegistry:
    """Registry of safe tools gated by PermissionGate + CapabilityBoundary."""

    def __init__(
        self,
        policy: ToolPolicyConfig,
        boundary: CapabilityBoundary,
    ) -> None:
        self.policy = policy
        self.boundary = boundary
        self.gate = PermissionGate(policy)
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def invoke(
        self,
        name: str,
        effective_privacy: Any,
        **kwargs: Any,
    ) -> ToolInvocation:
        from rdos.schemas.privacy import PrivacyLevel

        priv = PrivacyLevel(effective_privacy) if isinstance(effective_privacy, str) else effective_privacy
        decision = self.gate.evaluate(name, priv)

        if decision.requires_approval:
            return ToolInvocation(decision=decision, boundary=None, output=None)

        if not decision.allowed:
            return ToolInvocation(decision=decision, boundary=None, output=None)

        tool = self._tools.get(name)
        if tool is None:
            return ToolInvocation(
                decision=PermissionDecision(
                    tool_name=name,
                    permission_level="unknown",
                    allowed=False,
                    requires_approval=False,
                    reason=f"tool not registered: {name}",
                ),
                boundary=None,
                output=None,
            )

        # If the tool wants a path, run boundary check first.
        if "path" in kwargs:
            br = self.boundary.check_read(kwargs["path"])
            if not br.allowed:
                return ToolInvocation(decision=decision, boundary=br, output=None)
        else:
            br = None

        output = tool.run(**kwargs)
        return ToolInvocation(decision=decision, boundary=br, output=output)


def _no_op(_: Any) -> None:
    return None


def _callback_signature() -> Callable[..., None]:
    return _no_op
