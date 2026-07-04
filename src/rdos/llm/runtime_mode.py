"""LLM runtime mode resolution.

Modes:
- stub:  always StubLLMAdapter
- local: must use LocalLlamaCppAdapter; fail-hard on connection error
- auto:  try local first, fall back to stub with explicit warning
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from rdos.config import ModelsConfig
from rdos.llm.local_llama_cpp import LocalLlamaCppAdapter
from rdos.llm.provider import LLMAdapter, StubLLMAdapter


@dataclass
class LLMRuntimeDecision:
    mode: str
    adapter: LLMAdapter
    fallback_used: bool = False
    fallback_reason: str = ""
    warning: str = ""


def resolve_llm(cfg: ModelsConfig, mode: str) -> LLMRuntimeDecision:
    """Build the adapter for the requested mode."""
    if mode == "stub":
        return LLMRuntimeDecision(
            mode=mode,
            adapter=StubLLMAdapter(model="stub", provider="stub"),
        )

    if mode == "local":
        adapter = LocalLlamaCppAdapter.from_config(cfg, "local_fast")
        if not adapter.health():
            raise RuntimeError(
                "LLM mode='local' but local llama.cpp server is not reachable; "
                "use --llm-mode auto to allow fallback."
            )
        return LLMRuntimeDecision(mode=mode, adapter=adapter)

    if mode == "auto":
        try:
            adapter = LocalLlamaCppAdapter.from_config(cfg, "local_fast")
            if adapter.health():
                return LLMRuntimeDecision(mode=mode, adapter=adapter)
            return LLMRuntimeDecision(
                mode=mode,
                adapter=StubLLMAdapter(model="stub", provider="stub"),
                fallback_used=True,
                fallback_reason="local health-check returned False",
                warning="LLM mode=auto: local server health check failed; falling back to stub.",
            )
        except Exception as exc:  # noqa: BLE001
            return LLMRuntimeDecision(
                mode=mode,
                adapter=StubLLMAdapter(model="stub", provider="stub"),
                fallback_used=True,
                fallback_reason=str(exc)[:200],
                warning=f"LLM mode=auto: local adapter error ({exc!s:.120}); falling back to stub.",
            )

    raise ValueError(f"unknown llm-mode: {mode!r}; expected stub|local|auto")


def adapter_name(adapter: LLMAdapter) -> str:
    return type(adapter).__name__


def _env_default(key: str, default: str) -> str:
    return os.environ.get(key, default) or default


def _silence(_x: Any) -> None:  # pragma: no cover
    """Placeholder for future logging hooks."""
    return None
