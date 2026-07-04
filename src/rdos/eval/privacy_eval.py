"""Privacy routing eval — policy compliance + leakage rates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdos.config import RdosConfig
from rdos.eval.rag_eval import load_jsonl
from rdos.llm.privacy_router import PrivacyInput, PrivacyRouter
from rdos.schemas.document import DocumentChunk
from rdos.schemas.privacy import PrivacyLevel


def _make_chunk(level: PrivacyLevel) -> DocumentChunk:
    return DocumentChunk(
        doc_id="d",
        file_path="x",
        title="t",
        heading_path=[],
        chunk_id="c",
        chunk_text="x",
        token_count=1,
        content_hash="h",
        chunk_hash="h",
        privacy_level=level,
    )


def evaluate_privacy(
    cfg: RdosConfig,
    *,
    eval_set: str | Path = "eval_sets/privacy_routing.jsonl",
) -> dict[str, Any]:
    samples = load_jsonl(eval_set)
    if not samples:
        return {
            "metrics": {
                "privacy_policy_compliance": 0.0,
                "private_raw_leakage_rate": 0.0,
                "company_sensitive_leakage_rate": 0.0,
            },
            "samples": 0,
            "results": [],
        }

    router = PrivacyRouter(cfg.privacy_policy)
    compliant = 0
    private_raw_leaks = 0
    company_leaks = 0
    results: list[dict[str, Any]] = []

    for sample in samples:
        query_level = PrivacyLevel(sample["query_privacy"])
        retrieved_levels = [PrivacyLevel(p) for p in sample.get("retrieved_privacy", [])]
        retrieved_chunks = [_make_chunk(lv) for lv in retrieved_levels]
        decision = router.calculate_effective_privacy(
            PrivacyInput(
                user_query="eval",
                user_query_privacy=query_level,
                retrieved_chunks=retrieved_chunks,
            )
        )

        expected_eff = PrivacyLevel(sample["expected_effective"])
        is_compliant = decision.effective_privacy_level == expected_eff
        must_local = sample.get("must_local", False)
        external_allowed = sample.get("external_allowed", True)
        local_ok = (not must_local) or not decision.allows_external_model
        ext_ok = decision.allows_external_model == external_allowed
        all_ok = is_compliant and local_ok and ext_ok
        compliant += int(all_ok)

        # Leakage: effective level allows external when it shouldn't
        if decision.effective_privacy_level == PrivacyLevel.private_raw and decision.allows_external_model:
            private_raw_leaks += 1
        if (
            decision.effective_privacy_level == PrivacyLevel.company_sensitive
            and decision.allows_external_model
        ):
            company_leaks += 1

        results.append(
            {
                "query_privacy": sample["query_privacy"],
                "retrieved_privacy": sample.get("retrieved_privacy", []),
                "expected_effective": sample["expected_effective"],
                "actual_effective": decision.effective_privacy_level.value,
                "allows_external": decision.allows_external_model,
                "compliant": all_ok,
            }
        )

    n = len(samples)
    return {
        "metrics": {
            "privacy_policy_compliance": compliant / n,
            "private_raw_leakage_rate": private_raw_leaks / n,
            "company_sensitive_leakage_rate": company_leaks / n,
        },
        "samples": n,
        "results": results,
    }
