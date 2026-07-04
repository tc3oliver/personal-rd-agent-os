"""SQLite checkpointer factory for LangGraph runtime."""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver


class _OwnedSqliteSaver(SqliteSaver):
    """SqliteSaver that owns its connection and context manager.

    The default `SqliteSaver.from_conn_string()` returns a context manager
    that closes the conn on `__exit__`. We need to keep both alive for the
    lifetime of the runtime, so we hold an explicit reference here.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__(conn)
        self._owned_conn = conn

    def close(self) -> None:
        with contextlib.suppress(sqlite3.Error):
            self._owned_conn.close()


def build_sqlite_checkpointer(path: str | Path = "data/checkpoints.db") -> Any:
    """Build a SqliteSaver checkpointer at the given path.

    Caller owns the returned saver; call `.close()` when done (or let process
    exit). The connection stays open across graph invocations.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), check_same_thread=False)
    return _OwnedSqliteSaver(conn)
