"""Daily Digest app — summarize recent notes, cluster topics."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from rdos.config import RdosConfig
from rdos.rag.embedding import build_embedding_provider
from rdos.rag.hybrid_search import RetrievalFilters
from rdos.rag.retriever import HybridRetriever
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.research_apps import DigestOutput


def _recent_notes(store: SqliteMetadataStore, since: str) -> list[dict[str, Any]]:
    rows = store._conn.execute(  # noqa: SLF001  (read-only)
        """
        SELECT file_path, title, date, topic, source_collection, indexed_at
        FROM documents
        WHERE stale = 0 AND (date IS NOT NULL AND date >= ?)
        ORDER BY date DESC
        LIMIT 100
        """,
        (since,),
    ).fetchall()
    return [dict(r) for r in rows]


def _cluster_topics(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for n in notes:
        counter[n.get("topic") or "(none)"] += 1
    return [{"topic": t, "count": c} for t, c in counter.most_common(8)]


def _build_digest_output(
    *,
    since: str,
    notes: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    citations: list[Any],
    privacy: str,
) -> DigestOutput:
    return DigestOutput(
        date=since,
        notes=notes,
        clusters=clusters,
        suggested_ideas=_suggest_ideas(notes, clusters),
        citations=citations,
        privacy_level=privacy,
    )


def _suggest_ideas(notes: list[dict[str, Any]], clusters: list[dict[str, Any]]) -> list[str]:
    ideas: list[str] = []
    top = clusters[0]["topic"] if clusters else "(none)"
    ideas.append(f"把 {top} 主題的近期筆記整理成技術文章")
    if len(clusters) >= 2:
        ideas.append(f"比較 {clusters[0]['topic']} 與 {clusters[1]['topic']} 的設計取捨")
    ideas.append("把近期筆記對應到 RDOS 既有架構的優化方向")
    return ideas


def run_digest(
    *,
    cfg: RdosConfig,
    since: str,
    source_collection: str | None = None,
    embedding_provider: str | None = None,
) -> tuple[DigestOutput, str]:
    """Build a daily digest since YYYY-MM-DD."""
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    notes = _recent_notes(store, since)
    if source_collection:
        notes = [n for n in notes if n.get("source_collection") == source_collection]
    clusters = _cluster_topics(notes)

    # Cite top representative notes by searching across top topic
    citations: list[Any] = []
    if clusters:
        top_topic = clusters[0]["topic"]
        dim = cfg.models.embedding.dim or cfg.rag.embedding.dim
        vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=dim)
        emb = build_embedding_provider(
            embedding_provider or cfg.models.embedding.provider, dim=dim
        )
        retriever = HybridRetriever(
            sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg
        )
        result = retriever.search(top_topic, top_k=3, filters=RetrievalFilters())
        from rdos.rag.citation_builder import CitationBuilder

        citations = CitationBuilder(max_citations=3).build(top_topic, result)

    privacy = "private_raw" if not source_collection or source_collection == "clawd-research" else "public"
    out = _build_digest_output(
        since=since,
        notes=notes[:20],
        clusters=clusters,
        citations=citations,
        privacy=privacy,
    )

    # Write a markdown summary
    out_dir = Path("data/generated/digests")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    md_path = out_dir / f"digest_{ts}.md"
    md_path.write_text(_render_digest_md(out), encoding="utf-8")

    store.close()
    return out, str(md_path)


def _render_digest_md(out: DigestOutput) -> str:
    lines = [f"# Daily R&D Digest - {out.date}", ""]
    lines.append("## 新增主題")
    lines.append("")
    for c in out.clusters:
        lines.append(f"- {c['topic']} ({c['count']} 篇)")
    lines.append("")
    lines.append("## 重點筆記")
    lines.append("")
    for n in out.notes[:10]:
        lines.append(f"- [{n.get('date')}] {n.get('title')} (`{n.get('topic')}`)")
    lines.append("")
    lines.append("## 與既有研究關聯")
    lines.append("")
    for c in out.citations[:5]:
        lines.append(f"- {c.title} → {' > '.join(c.heading_path) or '-'}")
    lines.append("")
    lines.append("## 可延伸成工作提案的方向")
    lines.append("")
    for idea in out.suggested_ideas:
        lines.append(f"- {idea}")
    lines.append("")
    lines.append("## 可寫成文章的題目")
    lines.append("")
    if out.clusters:
        lines.append(f"- {out.clusters[0]['topic']} 的核心設計與實作取捨")
    if len(out.clusters) >= 2:
        lines.append(f"- {out.clusters[1]['topic']} 在 RDOS 的落地路徑")
    lines.append("")
    lines.append(f"_privacy_level: {out.privacy_level}_")
    return "\n".join(lines)
