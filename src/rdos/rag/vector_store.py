"""LanceDB vector store wrapper with provider metadata.

Embedding provider metadata (name / model / dim) is stored alongside the
vector schema. On search, mismatched provider/dim raises a typed error
instead of silently returning garbage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

from rdos.rag.embedding import EmbeddingProvider
from rdos.schemas.document import DocumentChunk


class EmbeddingProviderMismatchError(Exception):
    """Raised when query provider ≠ index provider."""


class EmbeddingDimensionMismatchError(Exception):
    """Raised when query embedding dim ≠ index dim."""


def _schema_for(dim: int) -> pa.Schema:
    """Fixed-size list schema so LanceDB recognizes the vector column."""
    return pa.schema(
        [
            pa.field("chunk_id", pa.string()),
            pa.field("chunk_hash", pa.string()),
            pa.field("doc_id", pa.string()),
            pa.field("heading_path", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), dim)),
        ]
    )


META_TABLE = "_embedding_meta"
META_KEYS = ("embedding_provider", "embedding_model", "embedding_dim")


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
            self._db.create_table(self.table_name, schema=_schema_for(self.dim))

    # ----- metadata -----

    def write_provider_meta(self, provider: EmbeddingProvider) -> None:
        """Persist provider identity so future search/ingest can detect mismatch."""
        meta_path = self.path / f"{META_TABLE}.json"
        payload = {
            "embedding_provider": provider.name,
            "embedding_model": provider.model,
            "embedding_dim": int(provider.dim),
        }
        meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_provider_meta(self) -> dict[str, Any]:
        meta_path = self.path / f"{META_TABLE}.json"
        if not meta_path.exists():
            return {}
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def ensure_provider_compatible(self, provider: EmbeddingProvider) -> None:
        """Raise if `provider` doesn't match the index's stored metadata."""
        meta = self.read_provider_meta()
        if not meta:
            # First ingestion: nothing to check.
            return
        if meta.get("embedding_provider") not in (None, provider.name):
            raise EmbeddingProviderMismatchError(
                f"index provider={meta['embedding_provider']!r} but query provider={provider.name!r}; "
                "reindex with the new provider or switch back."
            )
        if int(meta.get("embedding_dim", -1)) != int(provider.dim):
            raise EmbeddingDimensionMismatchError(
                f"index dim={meta['embedding_dim']} but query dim={provider.dim}; "
                "reindex with the new dim."
            )

    # ----- writes -----

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> int:
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        tbl = self._db.open_table(self.table_name)
        existing_hashes = self._existing_hashes(tbl)

        rows: list[dict[str, Any]] = []
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
        if len(query_vec) != self.dim:
            raise EmbeddingDimensionMismatchError(
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
        meta_path = self.path / f"{META_TABLE}.json"
        if meta_path.exists():
            meta_path.unlink()
        self._ensure_table()
