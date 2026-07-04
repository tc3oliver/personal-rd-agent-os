"""Model routing eval — does the router pick the expected profile?"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdos.config import RdosConfig
from rdos.eval.rag_eval import load_jsonl
from rdos.llm.model_router import ModelRouter, RoutingInput
from rdos.schemas.privacy import PrivacyLevel


def evaluate_model_routing(
    cfg: RdosConfig,
    *,
    eval_set: str | Path = "eval_sets/model_routing.jsonl",
) -> dict[str, Any]:
    samples = load_jsonl(eval_set)
    if not samples:
        return {
            "metric": "model_routing_correct_rate",
            "value": 0.0,
            "samples": 0,
            "results": [],
        }

    router = ModelRouter(cfg.models)
    correct = 0
    results: list[dict[str, Any]] = []

    for sample in samples:
        decision = router.select(
            RoutingInput(
                task_type=sample["task_type"],
                effective_privacy_level=PrivacyLevel(sample["privacy_level"]),
            )
        )
        ok_profile = decision.selected_profile == sample["expected_profile"]
        ok_provider = decision.provider == sample["expected_provider"]
        ok_confirmation = True
        if "expected_confirmation" in sample:
            ok_confirmation = decision.requires_user_confirmation == sample["expected_confirmation"]
        is_correct = ok_profile and ok_provider and ok_confirmation
        correct += int(is_correct)
        results.append(
            {
                "task_type": sample["task_type"],
                "privacy_level": sample["privacy_level"],
                "expected_profile": sample["expected_profile"],
                "actual_profile": decision.selected_profile,
                "actual_provider": decision.provider,
                "correct": is_correct,
            }
        )

    return {
        "metric": "model_routing_correct_rate",
        "value": correct / len(samples),
        "samples": len(samples),
        "results": results,
    }
