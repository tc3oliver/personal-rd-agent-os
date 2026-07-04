"""LanceDB vector store wrapper.

Stores chunk embeddings plus a chunk_id pointer. The LanceDB table mirrors
chunk_hash for idempotent re-index (delete-then-insert keyed by chunk_hash).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

from rdos.schemas.document import DocumentChunk

SCHEMA = pa.schema(
    [
        pa.field("chunk_id", pa.string()),
        pa.field("chunk_hash", pa.string()),
        pa.field("doc_id", pa.string()),
        pa.field("heading_path", pa.string()),  # JSON
        pa.field("vector", pa.list_(pa.float32(), -1)),
    ]
)


class LanceVectorStore:
    def __init__(
        self,
        path: str | Path = "data/lancedb",
        table_name: str = "chunks",
        dim: int = 1024,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.table_name = table_name
        self.dim = dim
        self._db = lancedb.connect(str(self.path))
        self._ensure_table()

    def _ensure_table(self) -> None:
        existing = self._db.table_names()
        if self.table_name not in existing:
            self._db.create_table(self.table_name, schema=SCHEMA)

    # ----- writes -----

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> int:
        """Insert chunks that are not already present (by chunk_hash).

        Returns number of rows actually inserted.
        """
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        tbl = self._db.open_table(self.table_name)
        existing_hashes = self._existing_hashes(tbl)

        rows: list[dict[str, Any]] = []
        import json

        for chunk, vec in zip(chunks, embeddings, strict=True):
            if chunk.chunk_hash in existing_hashes:
                continue
            if len(vec) != self.dim:
                raise ValueError(
                    f"vector dim mismatch: got {len(vec)}, expected {self.dim}"
                )
            rows.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "chunk_hash": chunk.chunk_hash,
                    "doc_id": chunk.doc_id,
                    "heading_path": json.dumps(chunk.heading_path),
                    "vector": [float(x) for x in vec],
                }
            )
        if rows:
            tbl.add(rows)
        return len(rows)

    def _existing_hashes(self, tbl: Any) -> set[str]:
        if tbl.count_rows() == 0:
            return set()
        rows = tbl.to_arrow().select(["chunk_hash"]).to_pylist()
        return {r["chunk_hash"] for r in rows}

    # ----- reads -----

    def search(
        self,
        query_vec: list[float],
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """Vector search. Returns list of (chunk_id, score)."""
        if len(query_vec) != self.dim:
            raise ValueError(
                f"query vector dim mismatch: got {len(query_vec)}, expected {self.dim}"
            )
        tbl = self._db.open_table(self.table_name)
        if tbl.count_rows() == 0:
            return []
        result = (
            tbl.search(query_vec)
            .metric("cosine")
            .select(["chunk_id"])
            .limit(top_k)
            .to_list()
        )
        return [(r["chunk_id"], float(r.get("_distance", 0.0))) for r in result]

    def count(self) -> int:
        tbl = self._db.open_table(self.table_name)
        return tbl.count_rows()

    def drop_table(self) -> None:
        if self.table_name in self._db.table_names():
            self._db.drop_table(self.table_name)
        self._ensure_table()
