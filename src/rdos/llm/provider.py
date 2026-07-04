"""LLM provider abstraction.

Batch 0 only declares the interface. Concrete adapters (local llama.cpp,
cloud OpenAI) arrive in later batches. The ModelRouter returns routing
decisions, NOT pre-bound tool models — so this interface intentionally
has no `bind_tools` method.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMMessage:
    """Single chat message."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Result of an LLM generation."""

    text: str
    model: str
    provider: str
    raw: dict[str, Any] | None = None
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str | None = None


class LLMAdapter(Protocol):
    """LLM provider contract.

    Implementations must NOT carry tool bindings in their constructor.
    The orchestrator decides if/when tools are attached; the ModelRouter
    only returns a routing decision (Batch 5).
    """

    @property
    def provider_name(self) -> str:
        ...

    @property
    def model_name(self) -> str:
        ...

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        ...


class StubLLMAdapter:
    """Trivial stub used by tests and early skeleton smoke checks.

    Returns a deterministic, content-aware canned response so workflows
    can be exercised end-to-end without a real model.
    """

    def __init__(self, model: str = "stub", provider: str = "stub") -> None:
        self._model = model
        self._provider = provider

    @property
    def provider_name(self) -> str:
        return self._provider

    @property
    def model_name(self) -> str:
        return self._model

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict[str, str] | None = None,
        **_kwargs: Any,
    ) -> LLMResponse:
        last = messages[-1] if messages else LLMMessage(role="user", content="")
        text = f"[stub:{self._model}] ack: {last.content[:200]}"
        return LLMResponse(
            text=text,
            model=self._model,
            provider=self._provider,
            usage={"prompt_tokens": len(last.content), "completion_tokens": len(text)},
            finish_reason="stop",
        )
