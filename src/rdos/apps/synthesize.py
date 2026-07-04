"""Research Synthesis app — citation-grounded multi-round synthesis."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from rdos.config import RdosConfig
from rdos.llm.provider import LLMAdapter, LLMMessage, StubLLMAdapter
from rdos.rag.citation_builder import CitationBuilder
from rdos.rag.citation_validator import CitationValidator
from rdos.rag.embedding import build_embedding_provider
from rdos.rag.hybrid_search import RetrievalFilters
from rdos.rag.retriever import HybridRetriever
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.research_apps import SynthesisClaim, SynthesisOutput


def _split_claims(text: str) -> list[str]:
    """Heuristic: each non-empty line that begins with a digit/bullet/dash is a claim."""
    claims: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^(?:\d+[.)]|[-*•]|[一二三四五六七八九十]+[、.])\s+", line):
            claims.append(re.sub(r"^(?:\d+[.)]|[-*•]|[一二三四五六七八九十]+[、.])\s+", "", line))
        elif len(line) > 12:
            claims.append(line)
    return claims[:8]


def _attach_citations(claims: list[str], citations: list[Any]) -> list[SynthesisClaim]:
    """Naive: each claim cites the first citation whose quote overlaps."""
    out: list[SynthesisClaim] = []
    for claim in claims:
        indices: list[int] = []
        claim_lower = claim.lower()
        for i, c in enumerate(citations):
            quote = (getattr(c, "quote", "") or "").lower()
            if not quote:
                continue
            # Match on any 4-char overlap from the quote.
            for j in range(0, max(0, len(quote) - 4), 5):
                if quote[j : j + 4] in claim_lower:
                    indices.append(i)
                    break
        out.append(
            SynthesisClaim(
                statement=claim,
                citation_indices=indices,
                confidence=0.5 + 0.1 * len(indices),
            )
        )
    return out


def run_synthesis(
    *,
    cfg: RdosConfig,
    question: str,
    source_collection: str | None = None,
    embedding_provider: str | None = None,
    llm: LLMAdapter | None = None,
) -> tuple[SynthesisOutput, str]:
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    dim = cfg.models.embedding.dim or cfg.rag.embedding.dim
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=dim)
    emb = build_embedding_provider(
        embedding_provider or cfg.models.embedding.provider, dim=dim
    )
    retriever = HybridRetriever(
        sqlite_store=store, vector_store=vectors, embedding=emb, config=cfg
    )

    used_llm = llm or StubLLMAdapter(model="stub", provider="stub")

    # Multi-round retrieval: pull 5, then pull 5 more with question + first batch titles.
    result1 = retriever.search(question, top_k=5, filters=RetrievalFilters())
    seed_titles = " ".join(c.title for c in result1.chunks[:3])
    result2 = retriever.search(
        f"{question} {seed_titles}", top_k=5, filters=RetrievalFilters()
    )
    merged_chunks: list[Any] = []
    seen: set[str] = set()
    for c in result1.chunks + result2.chunks:
        if c.chunk_id in seen:
            continue
        seen.add(c.chunk_id)
        merged_chunks.append(c)
    merged_chunks = merged_chunks[:8]

    class _Shim:
        chunks = merged_chunks

    citations = CitationBuilder(max_citations=8).build(question, _Shim())
    report = CitationValidator(store).validate_many(citations, merged_chunks)

    # Build context and ask LLM to draft claims
    context_parts: list[str] = []
    for i, c in enumerate(merged_chunks, 1):
        context_parts.append(
            f"[{i}] {c.title} :: {' > '.join(c.heading_path)}\nchunk_id={c.chunk_id}\n{c.chunk_text}"
        )
    context = "\n---\n".join(context_parts)

    system = (
        "You are a research synthesis assistant. Using ONLY the provided context, "
        "draft 3-6 distinct claims about the question. Each claim MUST cite the [N] "
        "index of the supporting chunk. If claims diverge, list both views. "
        "Output as a numbered list."
    )
    user = (
        f"Question: {question}\n\n"
        f"Context:\n{context}\n\n"
        f"Numbered claims:"
    )
    try:
        resp = used_llm.generate(
            [
                LLMMessage(role="system", content=system),
                LLMMessage(role="user", content=user),
            ]
        )
        raw = resp.text
    except Exception as exc:  # noqa: BLE001
        raw = f"(generation failed: {exc!s})"

    claim_strs = _split_claims(raw)
    claims = _attach_citations(claim_strs, citations)
    citation_coverage = (
        sum(1 for c in claims if c.citation_indices) / max(1, len(claims))
    )

    out = SynthesisOutput(
        question=question,
        summary=raw.split("\n\n")[0][:600],
        claims=claims,
        citations=citations,
        diverging_views=_find_diverging(claims),
        actionable_for_rdos=_actionable(question, claims),
        citation_coverage=citation_coverage,
        privacy_level="private_raw",
    )

    out_dir = Path("data/generated/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    md_path = out_dir / f"synthesis_{ts}.md"
    md_path.write_text(_render_synthesis_md(out, report.all_valid), encoding="utf-8")

    store.close()
    return out, str(md_path)


def _find_diverging(claims: list[SynthesisClaim]) -> list[str]:
    """Very small heuristic: if any two claims disagree on direction words."""
    out: list[str] = []
    opposites = [
        ("improve", "degrade"),
        ("better", "worse"),
        ("increase", "decrease"),
        ("true", "false"),
        ("yes", "no"),
    ]
    text = " ".join(c.statement.lower() for c in claims)
    for a, b in opposites:
        if a in text and b in text:
            out.append(f"同時出現 {a} / {b} 的對立用法，請人工確認")
    return out


def _actionable(question: str, claims: list[SynthesisClaim]) -> list[str]:
    out: list[str] = [
        "把這份 synthesis 的 claims 對應到 RDOS 的設計取捨",
        f"用「{question[:40]}」為題寫一篇技術文章",
    ]
    if any(not c.citation_indices for c in claims):
        out.append("為缺少 citation 的 claim 補充來源或標註假設")
    return out


def _render_synthesis_md(out: SynthesisOutput, all_citations_valid: bool) -> str:
    lines = ["# Research Synthesis", ""]
    lines.append(f"_Question: {out.question}_")
    lines.append("")
    lines.append("## 核心結論")
    lines.append("")
    lines.append(out.summary or "(no summary)")
    lines.append("")
    lines.append("## 主要資料來源")
    lines.append("")
    for i, c in enumerate(out.citations, 1):
        lines.append(
            f"[{i}] {c.title} → {' > '.join(c.heading_path) or '-'} "
            f"(`{c.chunk_id[:8]}`)"
        )
    lines.append("")
    lines.append("## 技術脈絡 (claims)")
    lines.append("")
    for i, claim in enumerate(out.claims, 1):
        cites = ", ".join(f"[{j + 1}]" for j in claim.citation_indices)
        lines.append(f"{i}. {claim.statement} {cites}".rstrip())
    lines.append("")
    lines.append("## 分歧觀點")
    lines.append("")
    for d in out.diverging_views or ["(none detected)"]:
        lines.append(f"- {d}")
    lines.append("")
    lines.append("## 可應用到 RDOS 的設計")
    lines.append("")
    for a in out.actionable_for_rdos:
        lines.append(f"- {a}")
    lines.append("")
    lines.append(f"_citation_coverage: {out.citation_coverage:.2%} | all_valid: {all_citations_valid}_")
    return "\n".join(lines)
