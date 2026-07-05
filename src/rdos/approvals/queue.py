"""SQLite-backed approval queue with replay protection."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rdos.approvals.models import ApprovalRequest

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    args TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    decision TEXT,
    decided_by TEXT,
    deny_reason TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    replay_count INTEGER DEFAULT 0,
    executed INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_approvals_decision ON approvals(decision);
CREATE INDEX IF NOT EXISTS idx_approvals_run_id ON approvals(run_id);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _idempotency_key(run_id: str, tool_name: str, args: dict[str, Any]) -> str:
    payload = json.dumps({"run_id": run_id, "tool": tool_name, "args": args}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ApprovalQueue:
    """Persistent approval queue in `data/approvals.db`."""

    def __init__(self, path: str | Path = "data/approvals.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ApprovalQueue:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ----- writes -----

    def request(
        self,
        *,
        run_id: str,
        thread_id: str,
        tool_name: str,
        args: dict[str, Any],
    ) -> tuple[ApprovalRequest, bool]:
        """Create a request. If idempotency_key exists, return existing.

        Returns (request, created) where `created` is False for replay.
        """
        key = _idempotency_key(run_id, tool_name, args)
        existing = self.get_by_key(key)
        if existing is not None:
            return existing, False

        approval_id = uuid.uuid4().hex
        req = ApprovalRequest(
            approval_id=approval_id,
            run_id=run_id,
            thread_id=thread_id,
            tool_name=tool_name,
            args=args,
            requested_at=_now_iso(),
            idempotency_key=key,
        )
        self._conn.execute(
            """
            INSERT INTO approvals
            (approval_id, run_id, thread_id, tool_name, args, requested_at,
             idempotency_key)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.approval_id,
                req.run_id,
                req.thread_id,
                req.tool_name,
                json.dumps(req.args, ensure_ascii=False),
                req.requested_at,
                req.idempotency_key,
            ),
        )
        self._conn.commit()
        return req, True

    def decide(
        self,
        approval_id: str,
        *,
        decision: str,
        decided_by: str = "cli",
        deny_reason: str | None = None,
    ) -> ApprovalRequest | None:
        if decision not in ("approved", "denied"):
            raise ValueError(f"decision must be 'approved' or 'denied', got {decision!r}")
        row = self._conn.execute(
            "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
        ).fetchone()
        if row is None:
            return None
        if row["decision"] is not None:
            # Already decided — return existing, do not overwrite.
            return _row_to_request(row)
        self._conn.execute(
            """
            UPDATE approvals
            SET decision = ?, decided_at = ?, decided_by = ?, deny_reason = ?
            WHERE approval_id = ?
            """,
            (decision, _now_iso(), decided_by, deny_reason, approval_id),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
        ).fetchone()
        return _row_to_request(row)

    def mark_executed(self, approval_id: str) -> None:
        self._conn.execute(
            "UPDATE approvals SET executed = 1, replay_count = replay_count + 1 "
            "WHERE approval_id = ?",
            (approval_id,),
        )
        self._conn.commit()

    # ----- reads -----

    def get(self, approval_id: str) -> ApprovalRequest | None:
        row = self._conn.execute(
            "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
        ).fetchone()
        return _row_to_request(row) if row else None

    def get_by_key(self, idempotency_key: str) -> ApprovalRequest | None:
        row = self._conn.execute(
            "SELECT * FROM approvals WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        return _row_to_request(row) if row else None

    def list_pending(self, limit: int = 50) -> list[ApprovalRequest]:
        rows = self._conn.execute(
            "SELECT * FROM approvals WHERE decision IS NULL ORDER BY requested_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_request(r) for r in rows]

    def list_recent(self, limit: int = 20) -> list[ApprovalRequest]:
        rows = self._conn.execute(
            "SELECT * FROM approvals ORDER BY requested_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_request(r) for r in rows]


def _row_to_request(row: sqlite3.Row) -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=row["approval_id"],
        run_id=row["run_id"],
        thread_id=row["thread_id"],
        tool_name=row["tool_name"],
        args=json.loads(row["args"] or "{}"),
        requested_at=row["requested_at"],
        decided_at=row["decided_at"],
        decision=row["decision"],
        decided_by=row["decided_by"],
        deny_reason=row["deny_reason"],
        idempotency_key=row["idempotency_key"],
        replay_count=row["replay_count"] or 0,
    )
