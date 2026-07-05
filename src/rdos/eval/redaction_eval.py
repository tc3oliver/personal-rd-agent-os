"""Redaction evaluator — recall + precision against known PII samples."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdos.eval.rag_eval import load_jsonl
from rdos.llm.redaction import load_redaction_config, redact

# Built-in PII samples for self-test (not user data).
DEFAULT_SAMPLES: list[dict[str, Any]] = [
    {"text": "聯絡我 alice@example.com", "expected_types": ["EMAIL"]},
    {"text": "我的手機 0912345678", "expected_types": ["PHONE-TW-MOBILE"]},
    {"text": "市話 02-23456789", "expected_types": ["PHONE-TW-AREA"]},
    {"text": "身分證 A123456789", "expected_types": ["ID-TW"]},
    {"text": "請見 https://example.com/foo", "expected_types": ["URL"]},
    {"text": "IP 是 192.168.1.1", "expected_types": ["IP"]},
    {"text": "卡號 4111 1111 1111 1111", "expected_types": ["CREDIT-CARD"]},
    {"text": "公司是 公司A 內部代號", "expected_types": ["COMPANY-HINT"], "company": "公司A"},
    {"text": "台北市信義路一段1號", "expected_types": ["ADDRESS-TW"]},
    {"text": "totally clean text without PII", "expected_types": []},
]


def evaluate_redaction(
    *,
    eval_set: str | Path | None = None,
    company_names: list[str] | None = None,
) -> dict[str, Any]:
    """Recall = caught expected_types / total expected. Precision = correct hits / total hits."""
    cfg = load_redaction_config()
    if company_names:
        cfg["company_names"] = company_names

    samples = load_jsonl(eval_set) if eval_set else DEFAULT_SAMPLES
    expected_total = 0
    caught = 0
    false_positives = 0
    total_hits = 0
    per_sample: list[dict[str, Any]] = []

    for s in samples:
        text = s["text"]
        expected_types = set(s.get("expected_types", []))
        # Override company names when sample specifies one
        if "company" in s:
            cfg_local = dict(cfg)
            cfg_local["company_names"] = [s["company"]]
        else:
            cfg_local = cfg
        _, recs = redact(text, cfg_local)
        caught_types = {r.type for r in recs}
        # Company hint shares namespace
        if expected_types & {"COMPANY-HINT"}:
            caught_company = any(r.type == "COMPANY-HINT" for r in recs)
            if caught_company:
                caught_types.add("COMPANY-HINT")
        if expected_types:
            expected_total += len(expected_types)
            caught += len(expected_types & caught_types)
            false_hits = caught_types - expected_types
            false_positives += len(false_hits)
            total_hits += len(recs)
        else:
            # No expected — all hits are false positives
            false_positives += len(recs)
            total_hits += len(recs)
        per_sample.append(
            {
                "text": text,
                "expected_types": sorted(expected_types),
                "caught_types": sorted(caught_types),
                "passed": expected_types.issubset(caught_types) and not (
                    caught_types - expected_types
                ),
            }
        )

    recall = caught / expected_total if expected_total else 1.0
    precision = (total_hits - false_positives) / total_hits if total_hits else 1.0
    return {
        "samples": len(samples),
        "redaction_recall": recall,
        "redaction_precision": precision,
        "expected_total": expected_total,
        "caught": caught,
        "false_positives": false_positives,
        "results": per_sample,
    }
