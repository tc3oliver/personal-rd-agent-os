"""SQLite-backed thread store."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rdos.threads.models import ThreadState, TurnRecord

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    closed_at TEXT,
    state TEXT NOT NULL,
    source_collection TEXT,
    privacy_level TEXT
);

CREATE INDEX IF NOT EXISTS idx_threads_created ON threads(created_at);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ThreadStore:
    def __init__(self, path: str | Path = "data/threads.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ThreadStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def create(
        self,
        *,
        source_collection: str = "",
        privacy_level: str = "private_raw",
    ) -> ThreadState:
        state = ThreadState(
            thread_id=uuid.uuid4().hex,
            created_at=_now_iso(),
            source_collection=source_collection,
            privacy_level=privacy_level,
        )
        self._conn.execute(
            "INSERT INTO threads (thread_id, created_at, state, source_collection, privacy_level) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                state.thread_id,
                state.created_at,
                state.model_dump_json(),
                state.source_collection,
                state.privacy_level,
            ),
        )
        self._conn.commit()
        return state

    def get(self, thread_id: str) -> ThreadState | None:
        row = self._conn.execute(
            "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        if row is None:
            return None
        return ThreadState(**json.loads(row["state"]))

    def update(self, state: ThreadState) -> None:
        self._conn.execute(
            "UPDATE threads SET state = ?, closed_at = ?, privacy_level = ? WHERE thread_id = ?",
            (
                state.model_dump_json(),
                state.closed_at,
                state.privacy_level,
                state.thread_id,
            ),
        )
        self._conn.commit()

    def close_thread(self, thread_id: str) -> ThreadState | None:
        state = self.get(thread_id)
        if state is None:
            return None
        state.closed_at = _now_iso()
        self.update(state)
        return state

    def list_recent(self, limit: int = 20) -> list[ThreadState]:
        rows = self._conn.execute(
            "SELECT * FROM threads ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [ThreadState(**json.loads(r["state"])) for r in rows]


def add_turn(
    store: ThreadStore,
    state: ThreadState,
    *,
    run_id: str,
    question: str,
    answer: str,
    citation_chunk_ids: list[str],
) -> TurnRecord:
    """Append a turn, update cited_chunks carry-forward, persist."""
    turn = TurnRecord(
        turn_index=len(state.turns),
        run_id=run_id,
        question=question,
        answer=answer,
        citation_chunk_ids=list(citation_chunk_ids),
        timestamp=_now_iso(),
    )
    state.turns.append(turn)
    # Carry forward cited chunks (dedup).
    seen = set(state.cited_chunks)
    for cid in citation_chunk_ids:
        if cid not in seen:
            state.cited_chunks.append(cid)
            seen.add(cid)
    store.update(state)
    return turn
