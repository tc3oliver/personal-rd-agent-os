"""SQLite metadata store for documents and chunks.

Schema is intentionally small; vector data lives in LanceDB. SQLite is the
source of truth for chunk existence checks during idempotent re-index.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from rdos.schemas.document import DocumentChunk, DocumentMetadata

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    title TEXT,
    date TEXT,
    tags TEXT,
    privacy_level TEXT,
    content_hash TEXT,
    indexed_at TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    title TEXT,
    heading_path TEXT,
    chunk_hash TEXT NOT NULL,
    chunk_text TEXT,
    token_count INTEGER,
    privacy_level TEXT,
    tags TEXT,
    date TEXT,
    content_hash TEXT,
    indexed_at TEXT,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE TABLE IF NOT EXISTS chunks_fts (
    chunk_id TEXT,
    chunk_text TEXT
);
"""


class SqliteMetadataStore:
    """Thin wrapper over a sqlite3 connection."""

    def __init__(self, path: str | Path = "data/sqlite/rdos.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SqliteMetadataStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ----- writes -----

    def upsert_document(self, meta: DocumentMetadata, indexed_at: str) -> None:
        self._conn.execute(
            """
            INSERT INTO documents (doc_id, file_path, title, date, tags, privacy_level,
                                   content_hash, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                file_path=excluded.file_path,
                title=excluded.title,
                date=excluded.date,
                tags=excluded.tags,
                privacy_level=excluded.privacy_level,
                content_hash=excluded.content_hash,
                indexed_at=excluded.indexed_at
            """,
            (
                meta.doc_id,
                meta.file_path,
                meta.title,
                meta.date,
                json.dumps(meta.tags),
                meta.privacy_level.value,
                meta.content_hash,
                indexed_at,
            ),
        )

    def insert_chunk(self, chunk: DocumentChunk, indexed_at: str) -> bool:
        """Insert a chunk. Returns False if chunk_id already exists (dedup case)."""
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO chunks
            (chunk_id, doc_id, file_path, title, heading_path, chunk_hash,
             chunk_text, token_count, privacy_level, tags, date, content_hash, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk.chunk_id,
                chunk.doc_id,
                chunk.file_path,
                chunk.title,
                json.dumps(chunk.heading_path),
                chunk.chunk_hash,
                chunk.chunk_text,
                chunk.token_count,
                chunk.privacy_level.value,
                json.dumps(chunk.tags),
                chunk.date,
                chunk.content_hash,
                indexed_at,
            ),
        )
        if cur.rowcount == 0:
            return False
        self._conn.execute(
            "INSERT OR IGNORE INTO chunks_fts (chunk_id, chunk_text) VALUES (?, ?)",
            (chunk.chunk_id, chunk.chunk_text),
        )
        return True

    def commit(self) -> None:
        self._conn.commit()

    # ----- reads -----

    def get_chunk(self, chunk_id: str) -> DocumentChunk | None:
        row = self._conn.execute("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()
        if not row:
            return None
        return _row_to_chunk(row)

    def chunk_exists_by_hash(self, chunk_hash: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM chunks WHERE chunk_hash = ? LIMIT 1", (chunk_hash,)
        ).fetchone()
        return row is not None

    def list_chunks_by_doc(self, doc_id: str) -> list[DocumentChunk]:
        rows = self._conn.execute(
            "SELECT * FROM chunks WHERE doc_id = ? ORDER BY chunk_id", (doc_id,)
        ).fetchall()
        return [_row_to_chunk(r) for r in rows]

    def all_chunks(self) -> list[DocumentChunk]:
        rows = self._conn.execute("SELECT * FROM chunks").fetchall()
        return [_row_to_chunk(r) for r in rows]

    def keyword_search(self, query: str, limit: int = 20) -> list[tuple[DocumentChunk, float]]:
        """FTS5 keyword search. Returns (chunk, score) pairs."""
        # Sanitize query — fts5 needs quotes/parens escaped
        safe = _sanitize_fts_query(query)
        if not safe:
            return []
        sql = """
            SELECT c.*, bm25(chunks_fts) AS score
            FROM chunks_fts
            JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """
        try:
            rows = self._conn.execute(sql, (safe, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [(_row_to_chunk(r), float(r["score"])) for r in rows]


def _row_to_chunk(row: sqlite3.Row) -> DocumentChunk:
    from rdos.schemas.privacy import PrivacyLevel

    return DocumentChunk(
        doc_id=row["doc_id"],
        file_path=row["file_path"],
        title=row["title"] or "",
        heading_path=json.loads(row["heading_path"] or "[]"),
        chunk_id=row["chunk_id"],
        chunk_text=row["chunk_text"] or "",
        token_count=row["token_count"] or 0,
        content_hash=row["content_hash"] or "",
        chunk_hash=row["chunk_hash"],
        privacy_level=PrivacyLevel(row["privacy_level"] or "private_raw"),
        tags=json.loads(row["tags"] or "[]"),
        date=row["date"],
    )


def _sanitize_fts_query(query: str) -> str:
    """Wrap each token in double quotes to avoid fts5 syntax errors."""
    tokens = [t for t in query.split() if t]
    if not tokens:
        return ""
    return " ".join(f'"{t.replace(chr(34), "")}"' for t in tokens)
