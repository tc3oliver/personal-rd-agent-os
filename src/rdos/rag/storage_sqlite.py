"""SQLite metadata store for documents and chunks.

Batch 12: documents table carries source_collection / topic / indexed_at /
stale / last_modified for incremental ingestion.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from rdos.schemas.document import DocumentChunk, DocumentMetadata
from rdos.schemas.privacy import PrivacyLevel

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    title TEXT,
    date TEXT,
    tags TEXT,
    privacy_level TEXT,
    content_hash TEXT,
    indexed_at TEXT,
    source_collection TEXT,
    topic TEXT,
    stale INTEGER DEFAULT 0,
    last_modified REAL
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
    source_collection TEXT,
    topic TEXT,
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
                                   content_hash, indexed_at, source_collection, topic,
                                   stale, last_modified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                file_path=excluded.file_path,
                title=excluded.title,
                date=excluded.date,
                tags=excluded.tags,
                privacy_level=excluded.privacy_level,
                content_hash=excluded.content_hash,
                indexed_at=excluded.indexed_at,
                source_collection=excluded.source_collection,
                topic=excluded.topic,
                stale=excluded.stale,
                last_modified=excluded.last_modified
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
                meta.source_collection,
                meta.topic,
                int(meta.stale),
                meta.last_modified,
            ),
        )

    def insert_chunk(self, chunk: DocumentChunk, indexed_at: str) -> bool:
        """Insert a chunk. Returns False if chunk_id already exists."""
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO chunks
            (chunk_id, doc_id, file_path, title, heading_path, chunk_hash,
             chunk_text, token_count, privacy_level, tags, date, content_hash,
             indexed_at, source_collection, topic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                chunk.source_collection,
                chunk.topic,
            ),
        )
        if cur.rowcount == 0:
            return False
        self._conn.execute(
            "INSERT OR IGNORE INTO chunks_fts (chunk_id, chunk_text) VALUES (?, ?)",
            (chunk.chunk_id, chunk.chunk_text),
        )
        return True

    def mark_stale_for_missing(self, present_doc_ids: set[str]) -> int:
        """Mark documents not in `present_doc_ids` as stale. Returns count marked."""
        if not present_doc_ids:
            # Mark everything stale.
            cur = self._conn.execute("UPDATE documents SET stale = 1 WHERE stale = 0")
            self._conn.commit()
            return cur.rowcount
        placeholders = ",".join("?" * len(present_doc_ids))
        cur = self._conn.execute(
            f"""
            UPDATE documents SET stale = 1
            WHERE doc_id NOT IN ({placeholders}) AND stale = 0
            """,
            tuple(present_doc_ids),
        )
        self._conn.commit()
        return cur.rowcount

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

    def get_document_by_path(self, file_path: str) -> DocumentMetadata | None:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE file_path = ? LIMIT 1", (file_path,)
        ).fetchone()
        if not row:
            return None
        return _row_to_document(row)

    def all_documents(self) -> list[DocumentMetadata]:
        rows = self._conn.execute("SELECT * FROM documents").fetchall()
        return [_row_to_document(r) for r in rows]

    def count_chunks_by_doc(self, doc_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM chunks WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        return int(row["n"]) if row else 0

    def keyword_search(self, query: str, limit: int = 20) -> list[tuple[DocumentChunk, float]]:
        """FTS keyword search. Returns (chunk, score) pairs."""
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
        source_collection=row["source_collection"] or "",
        topic=row["topic"] or "",
    )


def _row_to_document(row: sqlite3.Row) -> DocumentMetadata:
    return DocumentMetadata(
        doc_id=row["doc_id"],
        file_path=row["file_path"],
        title=row["title"] or "",
        date=row["date"],
        tags=json.loads(row["tags"] or "[]"),
        privacy_level=PrivacyLevel(row["privacy_level"] or "private_raw"),
        content_hash=row["content_hash"] or "",
        indexed_at=row["indexed_at"],
        source_collection=row["source_collection"] or "",
        topic=row["topic"] or "",
        stale=bool(row["stale"]),
        last_modified=row["last_modified"],
    )


def _sanitize_fts_query(query: str) -> str:
    """Wrap each token in double quotes to avoid fts5 syntax errors."""
    tokens = [t for t in query.split() if t]
    if not tokens:
        return ""
    return " ".join(f'"{t.replace(chr(34), "")}"' for t in tokens)
