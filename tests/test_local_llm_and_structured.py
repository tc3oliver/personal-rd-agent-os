"""Tests for local LLM adapter and structured output formatter."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from rdos.llm.local_llama_cpp import LocalLlamaCppAdapter
from rdos.llm.provider import LLMMessage, StubLLMAdapter
from rdos.llm.structured_output import (
    format_structured_output,
    generate_structured,
)


class Answer(BaseModel):
    yes: bool
    confidence: float


# ---- formatter ----


def test_format_structured_output_valid_json() -> None:
    parsed, result = format_structured_output('{"yes": true, "confidence": 0.9}', Answer)
    assert result.success
    assert parsed is not None
    assert parsed.yes is True
    assert parsed.confidence == 0.9


def test_format_structured_output_fenced_block() -> None:
    text = 'Here is the JSON:\n```json\n{"yes": false, "confidence": 0.1}\n```'
    parsed, result = format_structured_output(text, Answer)
    assert result.success
    assert parsed is not None
    assert parsed.yes is False


def test_format_structured_output_parse_error() -> None:
    parsed, result = format_structured_output("not json at all", Answer)
    assert not result.success
    assert parsed is None
    assert result.error is not None
    assert result.error.code == "json_parse_error"


def test_format_structured_output_validation_error() -> None:
    parsed, result = format_structured_output('{"yes": "maybe"}', Answer)
    assert not result.success
    assert parsed is None
    assert result.error is not None
    assert result.error.code == "validation_error"


# ---- generate_structured retry behavior ----


class _ScriptedAdapter(StubLLMAdapter):
    """Stub that returns scripted responses in order."""

    def __init__(self, responses: list[str]) -> None:
        super().__init__(model="scripted", provider="stub")
        self._responses = list(responses)
        self.calls = 0

    def generate(self, messages: list[LLMMessage], **kwargs: Any) -> Any:  # type: ignore[override]
        from rdos.llm.provider import LLMResponse

        text = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return LLMResponse(
            text=text,
            model=self._model,
            provider=self._provider,
            finish_reason="stop",
        )


def test_generate_structured_succeeds_first_try() -> None:
    adapter = _ScriptedAdapter(['{"yes": true, "confidence": 0.8}'])
    parsed, result = generate_structured(adapter, [LLMMessage(role="user", content="q")], Answer)
    assert result.success
    assert result.retries == 0
    assert parsed is not None and parsed.yes is True
    assert adapter.calls == 1


def test_generate_structured_retries_once_and_succeeds() -> None:
    adapter = _ScriptedAdapter(
        [
            "sorry, cannot help",
            '{"yes": true, "confidence": 0.6}',
        ]
    )
    parsed, result = generate_structured(adapter, [LLMMessage(role="user", content="q")], Answer)
    assert result.success
    assert result.retries == 1
    assert parsed is not None and parsed.yes is True
    assert adapter.calls == 2


def test_generate_structured_fails_after_retry_returns_error() -> None:
    adapter = _ScriptedAdapter(["not json", "still not json"])
    parsed, result = generate_structured(adapter, [LLMMessage(role="user", content="q")], Answer)
    assert not result.success
    assert parsed is None
    assert result.retries == 1
    assert result.error is not None
    assert result.error.code == "json_parse_error"


# ---- adapter config wiring ----


def test_local_adapter_from_config_picks_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from rdos.config import EmbeddingConfig, ModelsConfig, ProfileConfig

    monkeypatch.setenv("LOCAL_LLM_API_KEY", "fake-key")

    models = ModelsConfig(
        profiles={
            "local_fast": ProfileConfig(
                provider="local",
                base_url="http://test:1234",
                model="qwythos-9b-q4",
                api_key_env="LOCAL_LLM_API_KEY",
            )
        },
        embedding=EmbeddingConfig(provider="fake", dim=64),
    )
    adapter = LocalLlamaCppAdapter.from_config(models)
    assert adapter.model_name == "qwythos-9b-q4"
    assert adapter._base == "http://test:1234"
    assert adapter._api_key == "fake-key"


def test_adapter_health_returns_bool_when_unreachable() -> None:
    adapter = LocalLlamaCppAdapter(base_url="http://127.0.0.1:1", model="x")
    assert adapter.health() is False
