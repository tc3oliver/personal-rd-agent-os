"""Cloud send shim — mandatory pre-call hook for any future cloud adapter.

Audit P1-2: `prompt_privacy_validator.validate_prompt` existed but was
never invoked (dead code). This shim makes it LIVE: any cloud-bound
prompt MUST go through `cloud_send`. If the validator detects residual
PII / company hints, the call is blocked with `PrivacyBlockError`.

Today no cloud adapter ships in RDOS (intentionally local-first). When
one is added (post-v1.0), it must call `cloud_send` instead of bypassing.

Local adapters (LocalLlamaCppAdapter, StubLLMAdapter) do NOT need this
shim — local model calls never leave the host.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rdos.llm.prompt_privacy_validator import PrivacyValidation, validate_prompt
from rdos.llm.provider import LLMMessage


class PrivacyBlockError(Exception):
    """Raised when a cloud-bound prompt contains unredacted PII / company hints."""


@dataclass
class CloudSendResult:
    """Result of a cloud send attempt — caller MUST inspect `blocked`."""

    blocked: bool
    validation: PrivacyValidation
    reason: str = ""


def cloud_send(
    messages: list[LLMMessage],
    *,
    redaction_cfg: dict[str, Any] | None = None,
) -> CloudSendResult:
    """Pre-call hook for any external model invocation.

    Usage in a future cloud adapter:

        result = cloud_send(messages)
        if result.blocked:
            raise PrivacyBlockError(result.reason)
        # ... issue HTTP request ...

    Or shorter:

        cloud_send_or_raise(messages)
        # ... HTTP call ...
    """
    combined = " ".join(m.content for m in messages)
    validation = validate_prompt(combined, redaction_cfg)
    if not validation.allowed:
        return CloudSendResult(
            blocked=True,
            validation=validation,
            reason=f"prompt contains {validation.n_violations} unredacted recognition(s)",
        )
    return CloudSendResult(blocked=False, validation=validation)


def cloud_send_or_raise(
    messages: list[LLMMessage],
    *,
    redaction_cfg: dict[str, Any] | None = None,
) -> PrivacyValidation:
    """Convenience: raise PrivacyBlockError if any PII slips through."""
    result = cloud_send(messages, redaction_cfg=redaction_cfg)
    if result.blocked:
        raise PrivacyBlockError(result.reason)
    return result.validation
