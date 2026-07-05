"""Tests for Batch 18.5 — audit P1 fixes."""

from __future__ import annotations

from pathlib import Path

from rdos.eval.report import NO_ANSWER_GATE, REDACTION_GATE, RELEASE_GATE
from rdos.eval.structured_output_eval import evaluate_structured_output
from rdos.schemas.citation import Citation
from rdos.schemas.privacy import PrivacyLevel
from rdos.schemas.research import ResearchAnswer
from rdos.schemas.trace import TraceMetrics, TraceRecord
from rdos.trace.trace_store import JsonlTraceStore

# ---- P1-3: structured output measurement (no longer hardcoded) ----


def test_structured_output_eval_runs() -> None:
    out = evaluate_structured_output()
    assert out["metric"] == "structured_output_json_validity"
    assert out["samples"] >= 1
    assert 0.0 <= out["value"] <= 1.0


def test_structured_output_eval_round_trip_valid() -> None:
    """ResearchAnswer model_dump_json → model_validate_json must succeed."""
    out = evaluate_structured_output()
    # Default samples all valid → value = 1.0
    assert out["value"] == 1.0
    assert out["valid"] == out["samples"]


# ---- P1-1: adversarial eval aggregator ----


def test_adversarial_eval_files_exist() -> None:
    """Audit-confirmed: adversarial files actually exist on disk."""
    here = Path(__file__).resolve().parent.parent
    for name in (
        "privacy_routing_adversarial.jsonl",
        "model_routing_adversarial.jsonl",
        "citation_adversarial.jsonl",
    ):
        path = here / "eval_sets" / name
        assert path.exists(), f"missing adversarial eval set: {name}"


def test_adversarial_eval_files_have_content() -> None:
    here = Path(__file__).resolve().parent.parent
    for name in (
        "privacy_routing_adversarial.jsonl",
        "model_routing_adversarial.jsonl",
        "citation_adversarial.jsonl",
    ):
        path = here / "eval_sets" / name
        n = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        assert n >= 30, f"{name} has only {n} cases"


# ---- P1-2: trace redaction ----


def test_trace_redact_replaces_email(tmp_path: Path) -> None:
    """JsonlTraceStore redacts user_query before writing."""
    store = JsonlTraceStore(tmp_path / "runs.jsonl", redact=True)
    record = TraceRecord(
        run_id="r1",
        timestamp="2026-07-05T00:00:00Z",
        task_type="research_memory",
        user_query="email alice@example.com for details",
    )
    store.append(record)
    written = (tmp_path / "runs.jsonl").read_text(encoding="utf-8")
    assert "alice@example.com" not in written
    assert "REDACTED-EMAIL" in written


def test_trace_redact_replaces_phone(tmp_path: Path) -> None:
    store = JsonlTraceStore(tmp_path / "runs.jsonl", redact=True)
    record = TraceRecord(
        run_id="r2",
        timestamp="2026-07-05T00:00:00Z",
        task_type="research_memory",
        user_query="我的手機 0912345678 別打來",
    )
    store.append(record)
    written = (tmp_path / "runs.jsonl").read_text(encoding="utf-8")
    assert "0912345678" not in written


def test_trace_redact_marks_record(tmp_path: Path) -> None:
    store = JsonlTraceStore(tmp_path / "runs.jsonl", redact=True)
    record = TraceRecord(
        run_id="r3",
        timestamp="2026-07-05T00:00:00Z",
        task_type="research_memory",
        user_query="clean text without pii",
        metrics=TraceMetrics(),
    )
    store.append(record)
    listed = store.list_runs()
    assert listed
    assert listed[0].metrics.extra.get("redacted") is True


def test_trace_redact_can_be_disabled(tmp_path: Path) -> None:
    store = JsonlTraceStore(tmp_path / "runs.jsonl", redact=False)
    record = TraceRecord(
        run_id="r4",
        timestamp="2026-07-05T00:00:00Z",
        task_type="research_memory",
        user_query="email alice@example.com",
    )
    store.append(record)
    written = (tmp_path / "runs.jsonl").read_text(encoding="utf-8")
    assert "alice@example.com" in written


def test_trace_redact_final_answer_answer_field(tmp_path: Path) -> None:
    store = JsonlTraceStore(tmp_path / "runs.jsonl", redact=True)
    ans = ResearchAnswer(
        answer="reach me at alice@example.com",
        citations=[],
        confidence=0.5,
        selected_model_profile="local_fast",
        effective_privacy_level=PrivacyLevel.private_raw,
    )
    record = TraceRecord(
        run_id="r5",
        timestamp="2026-07-05T00:00:00Z",
        task_type="research_memory",
        user_query="q",
        final_answer=ans,
    )
    store.append(record)
    written = (tmp_path / "runs.jsonl").read_text(encoding="utf-8")
    assert "alice@example.com" not in written


def test_trace_redact_citation_quote(tmp_path: Path) -> None:
    store = JsonlTraceStore(tmp_path / "runs.jsonl", redact=True)
    cit = Citation(
        chunk_id="c", doc_id="d", file_path="x", title="t",
        heading_path=[], quote="contact alice@example.com please",
        chunk_hash="h",
    )
    record = TraceRecord(
        run_id="r6",
        timestamp="2026-07-05T00:00:00Z",
        task_type="research_memory",
        user_query="q",
        citations=[cit],
    )
    store.append(record)
    written = (tmp_path / "runs.jsonl").read_text(encoding="utf-8")
    assert "alice@example.com" not in written


# ---- P1-4: gate structures exist ----


def test_release_gate_unchanged() -> None:
    """Audit P1-4 must NOT have moved opt-in metrics into RELEASE_GATE."""
    assert "no_answer_accuracy" not in RELEASE_GATE
    assert "false_no_answer_rate" not in RELEASE_GATE
    assert "redaction_recall" not in RELEASE_GATE
    assert "redaction_precision" not in RELEASE_GATE
    assert len(RELEASE_GATE) == 8  # unchanged


def test_no_answer_gate_defined() -> None:
    assert NO_ANSWER_GATE["no_answer_accuracy"] == ("gte", 0.90)
    assert NO_ANSWER_GATE["false_no_answer_rate"] == ("lte", 0.05)


def test_redaction_gate_defined() -> None:
    assert REDACTION_GATE["redaction_recall"] == ("gte", 0.95)
    assert REDACTION_GATE["redaction_precision"] == ("gte", 0.95)


# ---- CLI smoke ----


def test_eval_cli_has_opt_in_subcommands() -> None:
    """`rdos eval` must expose no-answer / redaction / adversarial / structured-output."""
    from rdos.cli.eval import app

    # Typer exposes registered commands via registered_commands or similar
    cmds = {cmd.name for cmd in app.registered_commands}
    assert "no-answer" in cmds
    assert "redaction" in cmds
    assert "adversarial" in cmds
    assert "structured-output" in cmds
