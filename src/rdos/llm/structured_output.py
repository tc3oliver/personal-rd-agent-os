"""Structured output formatter — Pydantic-validated JSON, retry once on failure."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from rdos.llm.provider import LLMAdapter, LLMMessage

T = TypeVar("T", bound=BaseModel)


class StructuredError(BaseModel):
    code: str
    message: str
    raw_output: str


class StructuredResult(BaseModel):
    success: bool
    data: dict | None = None
    error: StructuredError | None = None
    retries: int = 0
    schema_name: str = ""


def _extract_json(text: str) -> str:
    """Best-effort extract a JSON object from LLM output."""
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    # Fenced code block
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    # Bare object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def _build_retry_prompt(original_prompt: str, raw: str, errors: list[str]) -> str:
    return (
        "Your previous response was not valid JSON or failed schema validation. "
        f"Errors: {errors[:3]}. "
        "Please return ONLY a JSON object that strictly matches the requested schema, "
        "with no prose before or after.\n\n"
        f"Previous response (truncated):\n{raw[:500]}"
    )


def format_structured_output(
    text: str,
    schema: type[T],
) -> tuple[T | None, StructuredResult]:
    """Try to parse + validate `text` as `schema`. Returns (parsed, result).

    Caller decides whether to retry using the result.error/retries fields.
    """
    raw_json = _extract_json(text)
    try:
        obj = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        result = StructuredResult(
            success=False,
            error=StructuredError(
                code="json_parse_error",
                message=str(exc),
                raw_output=text,
            ),
            retries=0,
            schema_name=schema.__name__,
        )
        return None, result

    try:
        parsed = schema.model_validate(obj)
    except ValidationError as exc:
        result = StructuredResult(
            success=False,
            error=StructuredError(
                code="validation_error",
                message=exc.json(),
                raw_output=text,
            ),
            retries=0,
            schema_name=schema.__name__,
        )
        return None, result

    result = StructuredResult(
        success=True,
        data=parsed.model_dump(mode="json"),
        retries=0,
        schema_name=schema.__name__,
    )
    return parsed, result


def generate_structured(
    adapter: LLMAdapter,
    messages: list[LLMMessage],
    schema: type[T],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> tuple[T | None, StructuredResult]:
    """Generate then validate. Retries once on failure with a corrective prompt.

    Returns (parsed | None, StructuredResult). On double-failure, success=False
    and error is set; caller must NOT raise on this — propagate the error.
    """
    response = adapter.generate(
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    parsed, result = format_structured_output(response.text, schema)
    if result.success:
        return parsed, result

    # Retry once
    retry_messages = list(messages) + [
        LLMMessage(role="assistant", content=response.text),
        LLMMessage(
            role="user",
            content=_build_retry_prompt(
                messages[-1].content if messages else "",
                response.text,
                [result.error.message] if result.error else [],
            ),
        ),
    ]
    response2 = adapter.generate(
        retry_messages,
        max_tokens=max_tokens,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    parsed, result2 = format_structured_output(response2.text, schema)
    result2.retries = 1
    return parsed, result2
