"""Topic Explorer app — explore a single topic across the corpus."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from rdos.config import RdosConfig
from rdos.rag.citation_builder import CitationBuilder
from rdos.rag.embedding import build_embedding_provider
from rdos.rag.hybrid_search import RetrievalFilters
from rdos.rag.retriever import HybridRetriever
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.research_apps import TopicExplorerOutput


def run_topic_explorer(
    *,
    cfg: RdosConfig,
    topic: str,
    source_collection: str | None = None,
    since: str | None = None,
    embedding_provider: str | None = None,
) -> tuple[TopicExplorerOutput, str]:
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    dim = cfg.models.embedding.dim or cfg.rag.embedding.dim
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=dim)
    emb = build_embedding_provider(
        embedding_provider or cfg.models.embedding.provider, dim=dim
    )
    retriever = HybridRetriever(
        sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg
    )

    result = retriever.search(topic, top_k=8, filters=RetrievalFilters())
    citations = CitationBuilder(max_citations=5).build(topic, result)

    representative = [
        {
            "title": c.title,
            "topic": getattr(c, "topic", ""),
            "file_path": c.file_path,
            "heading_path": list(c.heading_path),
            "chunk_id": c.chunk_id,
        }
        for c in result.chunks
    ]

    # Hot keywords from chunk text
    keyword_counter: Counter[str] = Counter()
    for c in result.chunks:
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", c.chunk_text):
            keyword_counter[tok] += 1
    hot_keywords = [t for t, _ in keyword_counter.most_common(12)]

    # Timeline from SQLite by topic match
    timeline: list[dict[str, Any]] = []
    rows = store._conn.execute(  # noqa: SLF001
        """
        SELECT date, title, file_path
        FROM documents
        WHERE stale = 0 AND topic LIKE ?
        ORDER BY date DESC
        LIMIT 10
        """,
        (f"%{topic}%",),
    ).fetchall()
    for r in rows:
        timeline.append({"date": r["date"], "title": r["title"], "file_path": r["file_path"]})

    # Related topics — pull via topic LIKE match
    related_rows = store._conn.execute(  # noqa: SLF001
        """
        SELECT DISTINCT topic FROM documents
        WHERE stale = 0 AND topic != ? AND topic != ''
        LIMIT 12
        """,
        (topic,),
    ).fetchall()
    related = [r["topic"] for r in related_rows if r["topic"]]

    # Blind spots: chunks retrieved but with no heading_path (might lack context)
    blind_spots: list[str] = []
    for c in result.chunks:
        if not c.heading_path:
            blind_spots.append(f"{c.title} 缺少 heading 結構")

    suggested = [
        f"寫一篇 {topic} 的深度回顧",
        f"把 {topic} 與 RDOS 既有模組結合",
        f"整理 {topic} 的反對意見與邊界案例",
    ]

    out = TopicExplorerOutput(
        topic=topic,
        representative_notes=representative,
        related_topics=related[:8],
        timeline=timeline,
        hot_keywords=hot_keywords,
        blind_spots=blind_spots,
        suggested_outputs=suggested,
        citations=citations,
    )

    # Render markdown
    out_dir = Path("data/generated/topics")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_topic = re.sub(r"[^A-Za-z0-9_-]", "_", topic)[:40]
    md_path = out_dir / f"topic_{safe_topic}_{ts}.md"
    md_path.write_text(_render_topic_md(out), encoding="utf-8")

    store.close()
    return out, str(md_path)


def _render_topic_md(out: TopicExplorerOutput) -> str:
    lines = [f"# Topic Explorer — {out.topic}", ""]
    lines.append("## 代表性筆記")
    lines.append("")
    for n in out.representative_notes[:5]:
        lines.append(
            f"- {n['title']} ({n.get('topic') or '-'})"
            f" — {' > '.join(n.get('heading_path') or [])}"
        )
    lines.append("")
    lines.append("## Timeline")
    lines.append("")
    for t in out.timeline[:8]:
        lines.append(f"- [{t['date']}] {t['title']}")
    lines.append("")
    lines.append("## Hot keywords")
    lines.append("")
    lines.append(", ".join(out.hot_keywords))
    lines.append("")
    lines.append("## Related topics")
    lines.append("")
    for r in out.related_topics:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## Blind spots")
    lines.append("")
    for b in out.blind_spots or ["(none)"]:
        lines.append(f"- {b}")
    lines.append("")
    lines.append("## Suggested outputs")
    lines.append("")
    for s in out.suggested_outputs:
        lines.append(f"- {s}")
    lines.append("")
    return "\n".join(lines)
