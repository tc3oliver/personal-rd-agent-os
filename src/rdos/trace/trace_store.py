"""JSONL-backed trace store.

Each run appends one JSONL record to data/traces/runs.jsonl. Records are
self-contained — one record per line, parseable independently.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rdos.schemas.trace import TraceError, TraceMetrics, TraceRecord


class JsonlTraceStore:
    def __init__(self, path: str | Path = "data/traces/runs.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Touch the file so list works on a fresh repo
        if not self.path.exists():
            self.path.touch()

    # ----- writes -----

    def append(self, record: TraceRecord) -> None:
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
