"""Local llama.cpp adapter — OpenAI-compatible chat completions.

Reads base_url + model from configs/models.yaml. Does NOT bind tools
(see ModelRouter contract). Falls back to a deterministic stub when the
local server is unreachable so offline development keeps working.
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from rdos.config import ModelsConfig, ProfileConfig
from rdos.llm.provider import LLMAdapter, LLMMessage, LLMResponse


class LocalLlamaCppAdapter(LLMAdapter):
    """OpenAI-compatible chat client for llama.cpp's `--server` mode."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._api_key = (
            api_key
            or os.environ.get("RDOS_LOCAL_MODEL_API_KEY")
            or os.environ.get("LOCAL_LLM_API_KEY", "local-dev-key")
        )
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return self._model

    @classmethod
    def from_config(cls, cfg: ModelsConfig, profile_name: str = "local_fast") -> LocalLlamaCppAdapter:
        profile: ProfileConfig = cfg.profiles[profile_name]
        api_key = os.environ.get(profile.api_key_env, "") if profile.api_key_env else None
        base_url = profile.base_url or "http://localhost:8080"
        return cls(base_url=base_url, model=profile.model, api_key=api_key)

    def health(self) -> bool:
        try:
            r = requests.get(f"{self._base}/health", timeout=self._timeout)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict[str, str] | None = None,
        enable_thinking: bool | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": m.role, "content": m.content, **({"name": m.name} if m.name else {})}
                for m in messages
            ],
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if response_format is not None:
            payload["response_format"] = response_format
        if enable_thinking is not None:
            payload["chat_template_kwargs"] = {"enable_thinking": enable_thinking}
        payload.update(kwargs)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        try:
            r = requests.post(
                f"{self._base}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as exc:
            return LLMResponse(
                text="",
                model=self._model,
                provider="local",
                raw={"error": str(exc)},
                finish_reason="error",
            )

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        text = msg.get("content") or ""
        usage = data.get("usage") or {}

        return LLMResponse(
            text=text,
            model=self._model,
            provider="local",
            raw=data,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            },
            finish_reason=choice.get("finish_reason"),
        )


def stream_chat(
    adapter: LocalLlamaCppAdapter,
    messages: list[LLMMessage],
    *,
    max_tokens: int = 1000,
) -> Any:
    """Yield content deltas from a streaming chat completion."""
    payload = {
        "model": adapter.model_name,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": True,
        "max_tokens": max_tokens,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {adapter._api_key}",
    }
    with requests.post(
        f"{adapter._base}/v1/chat/completions",
        headers=headers,
        json=payload,
        stream=True,
        timeout=adapter._timeout,
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            chunk = line[len("data: ") :]
            if chunk == "[DONE]":
                break
            try:
                obj = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            delta = ((obj.get("choices") or [{}])[0]).get("delta") or {}
            content = delta.get("content")
            if content:
                yield content
