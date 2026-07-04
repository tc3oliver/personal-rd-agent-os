"""LangChain compatibility probe for the local llama.cpp server.

Runs basic / streaming / JSON-mode / tool-calling / enable_thinking probes
via the langchain-openai ChatOpenAI adapter. Reports each as PASS / SKIP /
FAIL with a short reason.

Usage:
    uv run python scripts/check_langchain_llama_cpp.py
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any

DEFAULT_BASE_URL = os.environ.get("LOCAL_LLM_BASE_URL", "http://10.10.10.12:8080")
DEFAULT_MODEL = os.environ.get("LOCAL_LLM_MODEL", "qwythos-9b-q4")
DEFAULT_API_KEY = os.environ.get("LOCAL_LLM_API_KEY", "local-dev-key")


@dataclass
class Probe:
    name: str
    status: str   # PASS | SKIP | FAIL
    detail: str = ""


def _make_chat(**kwargs: Any) -> Any:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        base_url=DEFAULT_BASE_URL,
        model=DEFAULT_MODEL,
        api_key=DEFAULT_API_KEY,
        max_tokens=kwargs.pop("max_tokens", 1000),
        timeout=kwargs.pop("timeout", 60),
        **kwargs,
    )


def probe_basic() -> Probe:
    try:
        chat = _make_chat()
        resp = chat.invoke("Reply with the single word: pong")
        return Probe("basic_invoke", "PASS", repr(resp.content)[:120])
    except Exception as exc:  # noqa: BLE001
        return Probe("basic_invoke", "FAIL", str(exc)[:200])


def probe_streaming() -> Probe:
    try:
        chat = _make_chat()
        chunks = list(chat.stream("count slowly to 3"))
        return Probe("streaming", "PASS" if chunks else "FAIL", f"{len(chunks)} chunks")
    except Exception as exc:  # noqa: BLE001
        return Probe("streaming", "FAIL", str(exc)[:200])


def probe_json_mode() -> Probe:
    try:
        chat = _make_chat(model_kwargs={"response_format": {"type": "json_object"}})
        resp = chat.invoke('Return JSON {"ok": true}')
        # Will raise if not JSON
        json.loads(resp.content if isinstance(resp.content, str) else resp.content[0]["text"])
        return Probe("json_mode", "PASS", repr(resp.content)[:120])
    except Exception as exc:  # noqa: BLE001
        return Probe("json_mode", "FAIL", str(exc)[:200])


def probe_tool_calling() -> Probe:
    try:
        from langchain_core.tools import tool

        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        chat = _make_chat().bind_tools([add])
        resp = chat.invoke("What is 2 plus 3?")
        tool_calls = getattr(resp, "tool_calls", None) or []
        if tool_calls:
            return Probe("tool_calling", "PASS", f"{len(tool_calls)} call(s)")
        return Probe("tool_calling", "SKIP", "no tool_calls in response")
    except Exception as exc:  # noqa: BLE001
        return Probe("tool_calling", "SKIP", f"adapter error: {exc!s:.120}")


def probe_enable_thinking() -> Probe:
    try:
        chat = _make_chat(model_kwargs={"chat_template_kwargs": {"enable_thinking": False}})
        resp = chat.invoke("Reply with the single word: ack")
        return Probe("enable_thinking", "PASS", repr(resp.content)[:120])
    except Exception as exc:  # noqa: BLE001
        return Probe("enable_thinking", "SKIP", str(exc)[:200])


def main() -> int:
    probes = [
        probe_basic(),
        probe_streaming(),
        probe_json_mode(),
        probe_tool_calling(),
        probe_enable_thinking(),
    ]
    print(f"Probing {DEFAULT_BASE_URL} model={DEFAULT_MODEL}")
    print("-" * 60)
    for p in probes:
        print(f"{p.status:5} {p.name:18} {p.detail}")
    print("-" * 60)
    fails = [p for p in probes if p.status == "FAIL"]
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
