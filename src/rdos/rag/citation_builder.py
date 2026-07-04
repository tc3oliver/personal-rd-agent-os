"""Build Citation objects from retrieved chunks."""

from __future__ import annotations

import re

from rdos.rag.retriever import RetrievalResult
from rdos.schemas.citation import Citation


def _select_quote(chunk_text: str, query: str, max_chars: int = 160) -> str:
    """Pick the most query-relevant snippet from chunk_text."""
    if not chunk_text:
        return ""
    sentences = re.split(r"(?<=[\.!?。！？])\s+", chunk_text)
    if not sentences:
        return chunk_text[:max_chars]
    query_terms = {t.lower() for t in query.split() if len(t) > 1}
    if not query_terms:
        return sentences[0][:max_chars]

    best = sentences[0]
    best_score = -1
    for s in sentences:
        sl = s.lower()
        score = sum(1 for term in query_terms if term in sl)
        if score > best_score:
            best = s
            best_score = score
    snippet = best.strip()
    if len(snippet) > max_chars:
        snippet = snippet[: max_chars - 1].rstrip() + "…"
    return snippet


class CitationBuilder:
    """Turn retrieved chunks into Citation objects."""

    def __init__(self, max_citations: int = 5) -> None:
        self.max_citations = max_citations

    def build(self, query: str, result: RetrievalResult) -> list[Citation]:
        out: list[Citation] = []
        for chunk in result.chunks[: self.max_citations]:
            quote = _select_quote(chunk.chunk_text, query)
            out.append(
                Citation(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    file_path=chunk.file_path,
                    title=chunk.title,
                    heading_path=list(chunk.heading_path),
                    quote=quote,
                    chunk_hash=chunk.chunk_hash,
                    score=chunk.score,
                )
            )
        return out
