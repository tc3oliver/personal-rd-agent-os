"""Eval report — collate all metrics + gate verdict."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RELEASE_GATE = {
    "rag_recall_at_5": ("gte", 0.75),
    "citation_accuracy": ("gte", 0.70),
    "valid_chunk_reference_rate": ("gte", 0.95),
    "structured_output_json_validity": ("gte", 0.95),
    "model_routing_correct_rate": ("gte", 0.85),
    "privacy_policy_compliance": ("eq", 1.00),
    "private_raw_leakage_rate": ("eq", 0.00),
    "company_sensitive_leakage_rate": ("eq", 0.00),
}

# Batch 20: separate no-answer gate. Only enforced when threshold > 0
# (i.e., when the user has explicitly calibrated the framework).
# Foundation regression runs with no_answer_threshold=0, so no-answer
# accuracy is undefined; this gate is opt-in via `rdos eval no-answer`.
NO_ANSWER_GATE = {
    "no_answer_accuracy": ("gte", 0.90),
    "false_no_answer_rate": ("lte", 0.05),
}

# Batch 21: redaction gate. Opt-in via `rdos eval redaction`.
REDACTION_GATE = {
    "redaction_recall": ("gte", 0.95),
    "redaction_precision": ("gte", 0.95),
}


def _gate_check(name: str, value: float) -> tuple[bool, str]:
    op, threshold = RELEASE_GATE[name]
    if op == "gte":
        ok = value >= threshold
        return ok, f"{'>=' if ok else '<'} {threshold:.2f}"
    if op == "eq":
        ok = abs(value - threshold) < 1e-9
        return ok, f"{'=' if ok else '!='} {threshold:.2f}"
    raise ValueError(name)


def write_report(
    metrics: dict[str, float],
    results: dict[str, Any],
    *,
    out_path: str | Path = "data/reports/eval_report.md",
) -> tuple[bool, Path]:
    """Write markdown report. Returns (gate_passed, path)."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    gate_results: list[tuple[str, float, bool, str]] = []
    for name in RELEASE_GATE:
        if name not in metrics:
            gate_results.append((name, float("nan"), False, "missing"))
            continue
        ok, summary = _gate_check(name, metrics[name])
        gate_results.append((name, metrics[name], ok, summary))

    overall_pass = all(ok for _, _, ok, _ in gate_results)

    lines: list[str] = []
    lines.append("# RDOS Eval Report")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(UTC).isoformat()}_")
    lines.append("")
    lines.append("## Release Gate")
    lines.append("")
    lines.append("| Metric | Value | Target | Status |")
    lines.append("| --- | --- | --- | --- |")
    for name, value, ok, summary in gate_results:
        status = "PASS" if ok else "FAIL"
        op, threshold = RELEASE_GATE.get(name, ("?", 0.0))
        lines.append(
            f"| {name} | {value:.4f} | {op} {threshold:.2f} | {status} ({summary}) |"
        )
    lines.append("")
    lines.append(f"**Verdict: {'PASS' if overall_pass else 'FAIL'}**")
    lines.append("")

    # Per-eval sample failures
    for eval_name, payload in results.items():
        if not isinstance(payload, dict):
            continue
        results_list = payload.get("results") or payload.get("samples")
        if not isinstance(results_list, list):
            continue
        failures = [r for r in results_list if isinstance(r, dict) and not _is_pass(r)]
        if not failures:
            continue
        lines.append(f"## Failures — {eval_name}")
        lines.append("")
        for f in failures[:10]:
            lines.append(f"- `{f}`")
        lines.append("")

    p.write_text("\n".join(lines), encoding="utf-8")
    return overall_pass, p


def _is_pass(result: dict) -> bool:
    for key in ("hit", "accurate", "correct", "compliant"):
        if key in result:
            return bool(result[key])
    return True
