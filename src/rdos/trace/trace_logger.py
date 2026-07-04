"""Trace logging — wraps TraceStore with timing + uuid helpers."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from rdos.schemas.trace import TraceMetrics
from rdos.trace.trace_store import JsonlTraceStore, build_record_from_state


def new_run_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Timer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)


def record_run(
    store: JsonlTraceStore,
    state: dict,
    *,
    run_id: str | None = None,
    timestamp: str | None = None,
    timer: Timer | None = None,
) -> str:
    rid = run_id or new_run_id()
    ts = timestamp or now_iso()
    metrics = TraceMetrics(latency_ms=timer.elapsed_ms() if timer else None)
    record = build_record_from_state(state, run_id=rid, timestamp=ts, metrics=metrics)
    store.append(record)
    return rid
