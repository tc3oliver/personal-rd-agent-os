"""Indexing pipeline — orchestrates parser → chunker → sqlite + lancedb."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rdos.config import RdosConfig
from rdos.rag.chunker import chunk_document
from rdos.rag.embedding import EmbeddingProvider, build_embedding_provider
from rdos.rag.markdown_parser import parse_markdown_file
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.document import DocumentChunk


@dataclass
class IndexStats:
    documents_indexed: int
    chunks_inserted: int
    chunks_skipped: int
    sqlite_path: str
    lancedb_path: str
    elapsed_ms: int


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def index_directory(
    root: str | Path,
    config: RdosConfig | None = None,
    *,
    embedding: EmbeddingProvider | None = None,
    reset: bool = False,
) -> IndexStats:
    """Index every `.md` under `root`.

    Idempotent: re-running with the same files produces no new rows.
    """
    from rdos.config import get_config

    cfg = config or get_config()
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(f"index root not found: {root_path}")

    files = sorted(p for p in root_path.rglob("*.md") if p.is_file())

    sqlite_path = cfg.rag.storage.sqlite_path
    lancedb_path = cfg.rag.storage.lancedb_path
    dim = cfg.models.embedding.dim or cfg.rag.embedding.dim

    store = SqliteMetadataStore(sqlite_path)
    if embedding is None:
        embedding = build_embedding_provider(
            provider=cfg.models.embedding.provider,
            dim=dim,
        )
    else:
        # Trust the injected provider's dim if it exposes one.
        provider_dim = getattr(embedding, "dim", None)
        if provider_dim:
            dim = provider_dim
    vector_store = LanceVectorStore(lancedb_path, dim=dim)
    if reset:
        vector_store.drop_table()

    docs_indexed = 0
    chunks_inserted = 0
    chunks_skipped = 0
    started = time.perf_counter()

    try:
        for fp in files:
            meta, body = parse_markdown_file(fp)
            chunks = chunk_document(
                meta,
                body,
                target_min_tokens=cfg.rag.chunking.target_min_tokens,
                target_max_tokens=cfg.rag.chunking.target_max_tokens,
                overlap_sentences=cfg.rag.chunking.overlap_sentences,
                token_estimator=cfg.rag.chunking.token_estimator,
            )
            store.upsert_document(meta, indexed_at=_now_iso())

            new_chunks: list[DocumentChunk] = []
            for c in chunks:
                inserted = store.insert_chunk(c, indexed_at=_now_iso())
                if inserted:
                    new_chunks.append(c)
                else:
                    chunks_skipped += 1

            if new_chunks:
                texts = [c.chunk_text for c in new_chunks]
                vectors = embedding.embed(texts)
                vector_store.upsert_chunks(new_chunks, vectors)
                chunks_inserted += len(new_chunks)

            docs_indexed += 1
        store.commit()
    finally:
        store.close()

    elapsed = int((time.perf_counter() - started) * 1000)
    return IndexStats(
        documents_indexed=docs_indexed,
        chunks_inserted=chunks_inserted,
        chunks_skipped=chunks_skipped,
        sqlite_path=str(sqlite_path),
        lancedb_path=str(lancedb_path),
        elapsed_ms=elapsed,
    )
