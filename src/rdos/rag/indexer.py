"""Indexing pipeline — orchestrates parser → chunker → sqlite + lancedb.

Batch 12 additions:
- incremental index (content_hash check before re-chunking)
- source_collection / topic propagation
- privacy_default override
- index_report generation
- stale marking for missing files
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from rdos.config import RdosConfig
from rdos.rag.chunker import chunk_document
from rdos.rag.embedding import EmbeddingProvider, build_embedding_provider
from rdos.rag.markdown_parser import (
    derive_topic_from_path,
    parse_markdown_file,
)
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.document import DocumentChunk
from rdos.schemas.privacy import PrivacyLevel


@dataclass
class IndexStats:
    documents_indexed: int
    chunks_inserted: int
    chunks_skipped: int
    sqlite_path: str
    lancedb_path: str
    elapsed_ms: int
    embedding_provider: str = ""
    embedding_model: str = ""
    embedding_dim: int = 0
    # Batch 12:
    documents_created: int = 0
    documents_updated: int = 0
    documents_unchanged: int = 0
    documents_stale: int = 0
    source_collection: str = ""
    privacy_distribution: dict[str, int] = field(default_factory=dict)
    topic_distribution: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    slowest_files: list[tuple[str, int]] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _write_index_report(stats: IndexStats, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Index Report")
    lines.append("")
    lines.append(f"_Generated: {_now_iso()}_")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- documents indexed: {stats.documents_indexed}")
    lines.append(f"- documents created: {stats.documents_created}")
    lines.append(f"- documents updated: {stats.documents_updated}")
    lines.append(f"- documents unchanged: {stats.documents_unchanged}")
    lines.append(f"- documents stale: {stats.documents_stale}")
    lines.append(f"- chunks generated (new): {stats.chunks_inserted}")
    lines.append(f"- chunks skipped (dedup): {stats.chunks_skipped}")
    lines.append(f"- source_collection: `{stats.source_collection or 'n/a'}`")
    lines.append(f"- embedding_provider: `{stats.embedding_provider}` ({stats.embedding_model}, dim={stats.embedding_dim})")
    lines.append(f"- elapsed_ms: {stats.elapsed_ms}")
    lines.append("")
    lines.append("## Privacy distribution")
    lines.append("")
    lines.append("| Level | Count |")
    lines.append("| --- | --- |")
    for level, n in sorted(stats.privacy_distribution.items()):
        lines.append(f"| {level} | {n} |")
    lines.append("")
    lines.append("## Topic distribution (top 20)")
    lines.append("")
    lines.append("| Topic | Count |")
    lines.append("| --- | --- |")
    topic_counter = Counter(stats.topic_distribution)
    for topic, n in topic_counter.most_common(20):
        lines.append(f"| {topic or '(none)'} | {n} |")
    lines.append("")
    if stats.errors:
        lines.append("## Errors")
        lines.append("")
        for e in stats.errors[:50]:
            lines.append(f"- {e}")
        lines.append("")
    if stats.slowest_files:
        lines.append("## Slowest files (top 10)")
        lines.append("")
        lines.append("| File | ms |")
        lines.append("| --- | --- |")
        for fp, ms in stats.slowest_files[:10]:
            lines.append(f"| {fp} | {ms} |")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def index_directory(
    root: str | Path,
    config: RdosConfig | None = None,
    *,
    embedding: EmbeddingProvider | None = None,
    embedding_provider: str | None = None,
    reset: bool = False,
    source_collection: str | None = None,
    privacy_default: PrivacyLevel | str = PrivacyLevel.private_raw,
    report_path: str | Path | None = None,
) -> IndexStats:
    """Index every `.md` under `root` with incremental semantics."""
    from rdos.config import get_config

    cfg = config or get_config()
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(f"index root not found: {root_path}")

    files = sorted(p for p in root_path.rglob("*.md") if p.is_file())

    sqlite_path = cfg.rag.storage.sqlite_path
    lancedb_path = cfg.rag.storage.lancedb_path
    dim = cfg.models.embedding.dim or cfg.rag.embedding.dim
    provider_name = embedding_provider or cfg.models.embedding.provider

    if isinstance(privacy_default, str):
        privacy_default_level = PrivacyLevel(privacy_default)
    else:
        privacy_default_level = privacy_default

    store = SqliteMetadataStore(sqlite_path)
    if embedding is None:
        embedding = build_embedding_provider(provider=provider_name, dim=dim)
    else:
        provider_dim = getattr(embedding, "dim", None)
        if provider_dim:
            dim = provider_dim

    vector_store = LanceVectorStore(lancedb_path, dim=dim)
    if reset:
        vector_store.drop_table()
    vector_store.ensure_provider_compatible(embedding)
    vector_store.write_provider_meta(embedding)

    docs_indexed = 0
    docs_created = 0
    docs_updated = 0
    docs_unchanged = 0
    chunks_inserted = 0
    chunks_skipped = 0
    file_latencies: list[tuple[str, int]] = []
    errors: list[str] = []
    privacy_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()
    present_doc_ids: set[str] = set()
    started = time.perf_counter()

    try:
        for fp in files:
            file_started = time.perf_counter()
            try:
                topic = derive_topic_from_path(fp, root=root_path)
                meta, body = parse_markdown_file(
                    fp,
                    source_collection=source_collection,
                    topic=topic,
                    privacy_default=privacy_default_level,
                )
                present_doc_ids.add(meta.doc_id)

                existing = store.get_document_by_path(str(fp))
                if existing and existing.content_hash == meta.content_hash:
                    # unchanged: still bump indexed_at so it's not marked stale
                    existing.indexed_at = _now_iso()
                    existing.stale = False
                    store.upsert_document(existing, indexed_at=_now_iso())
                    docs_unchanged += 1
                    privacy_counter[existing.privacy_level.value] += 1
                    topic_counter[existing.topic] += 1
                    docs_indexed += 1
                    continue

                if existing:
                    docs_updated += 1
                else:
                    docs_created += 1

                chunks = chunk_document(
                    meta,
                    body,
                    target_min_tokens=cfg.rag.chunking.target_min_tokens,
                    target_max_tokens=cfg.rag.chunking.target_max_tokens,
                    overlap_sentences=cfg.rag.chunking.overlap_sentences,
                    token_estimator=cfg.rag.chunking.token_estimator,
                )
                # Propagate corpus provenance onto each chunk.
                for c in chunks:
                    c.source_collection = meta.source_collection
                    c.topic = meta.topic

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

                privacy_counter[meta.privacy_level.value] += 1
                topic_counter[meta.topic] += 1
                docs_indexed += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{fp}: {exc!s}")

            file_latencies.append((str(fp), int((time.perf_counter() - file_started) * 1000)))

        stale_marked = store.mark_stale_for_missing(present_doc_ids)
        store.commit()
    finally:
        store.close()

    file_latencies.sort(key=lambda kv: kv[1], reverse=True)

    elapsed = int((time.perf_counter() - started) * 1000)
    stats = IndexStats(
        documents_indexed=docs_indexed,
        chunks_inserted=chunks_inserted,
        chunks_skipped=chunks_skipped,
        sqlite_path=str(sqlite_path),
        lancedb_path=str(lancedb_path),
        elapsed_ms=elapsed,
        embedding_provider=embedding.name,
        embedding_model=embedding.model,
        embedding_dim=int(embedding.dim),
        documents_created=docs_created,
        documents_updated=docs_updated,
        documents_unchanged=docs_unchanged,
        documents_stale=stale_marked,
        source_collection=source_collection or "",
        privacy_distribution=dict(privacy_counter),
        topic_distribution=dict(topic_counter),
        errors=errors,
        slowest_files=file_latencies[:10],
    )

    if report_path is not None:
        _write_index_report(stats, Path(report_path))

    return stats
