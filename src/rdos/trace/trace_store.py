"""JSONL-backed trace store with optional redaction (audit P1-2).

Each run appends one JSONL record to data/traces/runs.jsonl. Records are
self-contained — one record per line, parseable independently.

Batch 18.5 (audit P1-2): `redact=True` (default) scrubs user_query /
final_answer / citation quotes against configs/redaction.yaml recognizers
before writing to disk. Set `redact=False` for debug / dev runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rdos.schemas.trace import TraceError, TraceMetrics, TraceRecord


class JsonlTraceStore:
    def __init__(
        self,
        path: str | Path = "data/traces/runs.jsonl",
        *,
        redact: bool = True,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Touch the file so list works on a fresh repo
        if not self.path.exists():
            self.path.touch()
        self.redact = redact

    # ----- writes -----

    def append(self, record: TraceRecord) -> None:
        if self.redact:
            record = _redact_record(record)
        line = record.model_dump_json()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # ----- reads -----

    def list_runs(self, limit: int = 20) -> list[TraceRecord]:
        records = self._read_all()
        return records[-limit:][::-1]  # most recent first

    def get(self, run_id: str) -> TraceRecord | None:
        for rec in self._read_all():
            if rec.run_id == run_id:
                return rec
        return None

    def _read_all(self) -> list[TraceRecord]:
        out: list[TraceRecord] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                out.append(TraceRecord(**obj))
        return out


# ----- helpers to build TraceRecord from graph state -----


def build_record_from_state(
    state: dict[str, Any],
    *,
    run_id: str,
    timestamp: str,
    metrics: TraceMetrics | None = None,
    errors: list[TraceError] | None = None,
) -> TraceRecord:
    """Convert a research_memory_graph state dict into a TraceRecord."""
    privacy_decision = state.get("privacy_decision")
    model_routing = state.get("model_routing")
    citations = state.get("citations") or []
    retrieved_chunks = state.get("retrieved_chunks") or []

    return TraceRecord(
        run_id=run_id,
        timestamp=timestamp,
        task_type=state.get("task_type", "research_memory"),
        user_query=state.get("user_query", ""),
        privacy_decision=privacy_decision,
        effective_privacy_level=(
            privacy_decision.effective_privacy_level.value if privacy_decision else None
        ),
        model_routing_decision=model_routing,
        retrieved_doc_ids=state.get("retrieved_doc_ids") or [],
        retrieved_chunks=[
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "heading_path": list(c.heading_path),
                "chunk_hash": c.chunk_hash,
                "score": c.score,
            }
            for c in retrieved_chunks
        ],
        citations=citations,
        citation_report=state.get("citation_report"),
        final_answer=state.get("final_answer"),
        structured_output=state.get("structured_payload"),
        metrics=metrics or TraceMetrics(),
        errors=errors or [],
    )


# ----- redaction (audit P1-2) -----


def _redact_record(record: TraceRecord) -> TraceRecord:
    """Scrub user_query / final_answer / citation quotes in-place.

    Best-effort: if redaction import fails (e.g., test environment
    without configs/redaction.yaml), return the record unchanged.
    """
    try:
        from rdos.llm.redaction import load_redaction_config
        from rdos.llm.redaction import redact as _redact

        cfg = load_redaction_config()
        if record.user_query:
            record.user_query, _ = _redact(record.user_query, cfg)
        if record.final_answer and record.final_answer.answer:
            new_ans, _ = _redact(record.final_answer.answer, cfg)
            record.final_answer.answer = new_ans
        for c in record.citations:
            if c.quote:
                c.quote, _ = _redact(c.quote, cfg)
        # Mark record as redacted for downstream consumers
        record.metrics.extra["redacted"] = True
    except Exception as exc:  # noqa: BLE001
        # Don't crash trace write if redaction fails — log and proceed.
        record.metrics.extra["redaction_error"] = str(exc)[:200]
    return record
