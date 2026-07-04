"""Knowledge tools — search_notes, read_note, list_recent_notes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdos.rag.hybrid_search import RetrievalFilters
from rdos.rag.retriever import HybridRetriever
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.schemas.privacy import PrivacyLevel


@dataclass
class _ToolMeta:
    name: str
    description: str


class SearchNotesTool:
    name = "search_notes"
    description = "Hybrid search across indexed notes; returns top_k chunks with citations."

    def __init__(self, retriever: HybridRetriever) -> None:
        self.retriever = retriever

    def run(self, *, query: str, top_k: int = 5, **_kwargs: Any) -> dict[str, Any]:
        result = self.retriever.search(query, top_k=top_k, filters=RetrievalFilters())
        return {
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "file_path": c.file_path,
                    "title": c.title,
                    "heading_path": list(c.heading_path),
                    "score": c.score,
                    "privacy_level": c.privacy_level.value,
                }
                for c in result.chunks
            ],
            "no_answer_triggered": result.no_answer_triggered,
            "latency_ms": result.retrieval_latency_ms,
        }


class ReadNoteTool:
    name = "read_note"
    description = "Read a single note file from an allowed root. Path must resolve inside allowed_roots."

    def __init__(self, *, max_bytes: int = 1 * 1024 * 1024) -> None:
        self.max_bytes = max_bytes

    def run(self, *, path: str, **_kwargs: Any) -> dict[str, Any]:
        # Boundary check is enforced by ToolRegistry.invoke before we get here.
        p = Path(path)
        text = p.read_text(encoding="utf-8", errors="replace")
        return {
            "path": str(p.resolve()),
            "size": len(text),
            "content": text,
        }


class ListRecentNotesTool:
    name = "list_recent_notes"
    description = "List recently indexed notes from the SQLite store, most recent first."

    def __init__(self, store: SqliteMetadataStore) -> None:
        self.store = store

    def run(self, *, limit: int = 20, **_kwargs: Any) -> dict[str, Any]:
        rows = self.store._conn.execute(  # noqa: SLF001  (read-only)
            """
            SELECT file_path, title, date, topic, source_collection, indexed_at
            FROM documents
            WHERE stale = 0
            ORDER BY indexed_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        return {
            "notes": [
                {
                    "file_path": r["file_path"],
                    "title": r["title"],
                    "date": r["date"],
                    "topic": r["topic"],
                    "source_collection": r["source_collection"],
                    "indexed_at": r["indexed_at"],
                }
                for r in rows
            ],
            "count": len(rows),
        }


def _silence(_: Any) -> PrivacyLevel | None:
    return None
