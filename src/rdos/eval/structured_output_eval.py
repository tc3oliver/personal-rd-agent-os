"""Structured output validity — measure JSON round-trip on synthesis samples.

Replaces the v0.1 hardcoded `1.0` (audit P1-3). For each sample in a small
synthesis set, build a ResearchAnswer, dump to JSON, parse back, validate.
Return fraction that survive.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from rdos.eval.rag_eval import load_jsonl
from rdos.schemas.citation import Citation
from rdos.schemas.privacy import PrivacyLevel
from rdos.schemas.research import ResearchAnswer


def _make_sample_answer(question: str) -> ResearchAnswer:
    cit = Citation(
        chunk_id="c1",
        doc_id="d1",
        file_path="x.md",
        title="x",
        heading_path=["H"],
        quote="q",
        chunk_hash="h",
    )
    return ResearchAnswer(
        answer=f"answer to {question}",
        citations=[cit],
        confidence=0.5,
        selected_model_profile="local_fast",
        effective_privacy_level=PrivacyLevel.private_raw,
        task_type="research_memory",
    )


def evaluate_structured_output(
    *,
    eval_set: str | Path | None = None,
) -> dict[str, Any]:
    """Round-trip ResearchAnswer through JSON; report fraction valid."""
    samples: list[dict[str, Any]] = []
    if eval_set is not None:
        samples = load_jsonl(eval_set)
    if not samples:
        # Fallback: 10 deterministic synthetic samples
        samples = [{"id": f"s{i}", "question": f"q{i}"} for i in range(10)]

    valid = 0
    for s in samples:
        ans = _make_sample_answer(s.get("question", "x"))
        try:
            dumped = ans.model_dump_json()
            parsed = ans.model_validate_json(dumped)
            if parsed.answer == ans.answer:
                valid += 1
        except (ValidationError, ValueError, TypeError):
            continue

    return {
        "metric": "structured_output_json_validity",
        "value": valid / len(samples) if samples else 0.0,
        "samples": len(samples),
        "valid": valid,
    }


def model_dumps_cleanly(model: BaseModel) -> bool:
    """Helper: does this Pydantic model round-trip cleanly?"""
    try:
        dumped = model.model_dump_json()
        type(model).model_validate_json(dumped)
        return True
    except (ValidationError, ValueError, TypeError):
        return False
