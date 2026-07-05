"""Prompt privacy validator — last line of defense before cloud call.

If any recognizer fires on a prompt about to be sent to a cloud model,
block the call and return a structured error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rdos.llm.redaction import load_redaction_config, scan


@dataclass
class PrivacyValidation:
    allowed: bool
    violations: list[str]
    n_violations: int


def validate_prompt(text: str, cfg: dict[str, Any] | None = None) -> PrivacyValidation:
    """If any recognizer fires, the prompt is unsafe for cloud."""
    cfg = cfg or load_redaction_config()
    recs = scan(text, cfg)
    if not recs:
        return PrivacyValidation(allowed=True, violations=[], n_violations=0)
    violations = [f"{r.type}@{r.start}-{r.end}: {r.text[:60]!r}" for r in recs]
    return PrivacyValidation(
        allowed=False, violations=violations, n_violations=len(recs)
    )
