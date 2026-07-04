"""Heading-aware chunker.

Splits a Markdown body into `DocumentChunk`s. Each chunk carries:
- heading_path: list of headings from root to current
- chunk_hash: hash of (chunk_text + heading_path + doc_id) for stable dedup
- content_hash: hash of full document body (propagated from parser)

Chunk boundaries are formed by:
1. Pre-splitting on each heading.
2. Further splitting any oversized section on paragraph boundaries to stay
   within `target_max_tokens`.
3. Gluing consecutive too-small paragraphs (within the same heading section)
   back together until reaching `target_min_tokens`.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from markdown_it import MarkdownIt

from rdos.schemas.document import DocumentChunk, DocumentMetadata


def estimate_tokens(text: str, mode: str = "char4") -> int:
    """Cheap token estimator."""
    if mode == "char4":
        return max(1, len(text) // 4)
    if mode == "char3":
        return max(1, len(text) // 3)
    if mode == "words":
        return max(1, len(text.split()))
    raise ValueError(f"unknown estimator mode: {mode!r}")


_HEADING_PREFIX = "#"


def _build_sections(body: str) -> list[tuple[list[str], str]]:
    """Split body into (heading_path, text) sections.

    A heading changes the current path: level N heading replaces the Nth
    element (and truncates deeper levels). Non-heading lines are appended
    to the current section.
    """
    sections: list[tuple[list[str], str]] = []
    path: list[str] = []
    current_lines: list[str] = []

    def flush() -> None:
        text = "\n".join(current_lines).strip()
        if text:
            sections.append((list(path), text))
        current_lines.clear()

    for line in body.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(_HEADING_PREFIX):
            level = 0
            for ch in stripped:
                if ch == _HEADING_PREFIX:
                    level += 1
                else:
                    break
            if 1 <= level <= 6 and (len(stripped) > level and stripped[level] == " "):
                title = stripped[level + 1 :].strip().rstrip("#").strip()
                flush()
                path = path[: level - 1]
                # pad with empty headings if jumped levels
                while len(path) < level - 1:
                    path.append("")
                if len(path) == level - 1:
                    path.append(title)
                else:
                    path[level - 1] = title
                # Include the heading text in the section so keyword search can match it
                current_lines.append(title)
                continue
        current_lines.append(line)

    flush()
    return sections


def _split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in re_split_paragraphs(text)]
    return [p for p in parts if p]


def re_split_paragraphs(text: str) -> list[str]:
    """Split on blank lines, preserving fenced code blocks intact."""
    chunks: list[str] = []
    buf: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if not in_fence:
                in_fence = True
                fence_marker = stripped[:3]
            elif stripped.startswith(fence_marker):
                in_fence = False
                fence_marker = ""
        if not line.strip() and not in_fence:
            if buf:
                chunks.append("\n".join(buf))
                buf = []
        else:
            buf.append(line)
    if buf:
        chunks.append("\n".join(buf))
    return chunks


def _chunk_hash(doc_id: str, heading_path: list[str], chunk_text: str) -> str:
    h = hashlib.sha256()
    h.update(doc_id.encode("utf-8"))
    h.update(b"|")
    h.update("/".join(heading_path).encode("utf-8"))
    h.update(b"|")
    h.update(chunk_text.encode("utf-8"))
    return h.hexdigest()


def _short_uuid(seed: str) -> str:
    """Deterministic chunk_id from a seed (avoids duplicates on re-index)."""
    return uuid.UUID(bytes=hashlib.md5(seed.encode("utf-8")).digest(), version=4).hex


def chunk_document(
    meta: DocumentMetadata,
    body: str,
    *,
    target_min_tokens: int = 300,
    target_max_tokens: int = 600,
    overlap_sentences: int = 1,
    token_estimator: str = "char4",
) -> list[DocumentChunk]:
    """Chunk a document into heading-aware chunks."""
    md = MarkdownIt("commonmark", {"html": False})

    sections = _build_sections(body)
    raw_chunks: list[tuple[list[str], str]] = []

    for heading_path, section_text in sections:
        paragraphs = _split_paragraphs(section_text)
        if not paragraphs:
            continue

        # Greedy merge paragraphs up to target_min_tokens,
        # but split if a single merged unit exceeds target_max_tokens.
        buf: list[str] = []
        buf_tokens = 0
        for para in paragraphs:
            para_tokens = estimate_tokens(para, mode=token_estimator)
            if buf and buf_tokens + para_tokens > target_max_tokens:
                raw_chunks.append((list(heading_path), "\n\n".join(buf)))
                # Optional overlap: keep last N paragraphs
                if overlap_sentences > 0 and len(buf) >= overlap_sentences:
                    buf = buf[-overlap_sentences:]
                    buf_tokens = sum(estimate_tokens(p, mode=token_estimator) for p in buf)
                else:
                    buf = []
                    buf_tokens = 0
            if buf_tokens + para_tokens > target_max_tokens and not buf:
                # Single paragraph is too large — hard-split by sentences.
                for piece in _hard_split_long_paragraph(para, target_max_tokens, token_estimator):
                    raw_chunks.append((list(heading_path), piece))
                continue
            buf.append(para)
            buf_tokens += para_tokens

        if buf:
            raw_chunks.append((list(heading_path), "\n\n".join(buf)))

    chunks: list[DocumentChunk] = []
    for heading_path, chunk_text in raw_chunks:
        clean = render_plain(md, chunk_text)
        if not clean.strip():
            continue
        token_count = estimate_tokens(clean, mode=token_estimator)
        c_hash = _chunk_hash(meta.doc_id, heading_path, clean)
        chunk_id = _short_uuid(c_hash)
        chunks.append(
            DocumentChunk(
                doc_id=meta.doc_id,
                file_path=meta.file_path,
                title=meta.title,
                heading_path=heading_path,
                chunk_id=chunk_id,
                chunk_text=clean,
                token_count=token_count,
                content_hash=meta.content_hash,
                chunk_hash=c_hash,
                privacy_level=meta.privacy_level,
                tags=list(meta.tags),
                date=meta.date,
            )
        )

    return chunks


def render_plain(md: MarkdownIt, text: str) -> str:
    """Render markdown to plain inline text (used as chunk_text)."""
    tokens = md.parse(text, {})
    parts: list[str] = []
    for tok in tokens:
        if tok.type == "inline" or tok.type in ("fence", "code_block"):
            parts.append(tok.content)
    return "\n".join(parts).strip()


def _hard_split_long_paragraph(para: str, target_max_tokens: int, mode: str) -> list[str]:
    """Split an oversized paragraph on sentence boundaries."""
    sentences = re_split_sentences(para)
    out: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    for s in sentences:
        s_tokens = estimate_tokens(s, mode=mode)
        if buf and buf_tokens + s_tokens > target_max_tokens:
            out.append(" ".join(buf))
            buf = [s]
            buf_tokens = s_tokens
        else:
            buf.append(s)
            buf_tokens += s_tokens
    if buf:
        out.append(" ".join(buf))
    return out or [para]


def re_split_sentences(text: str) -> list[str]:
    """Very small sentence splitter (CJK + ASCII aware)."""
    parts = re.split(r"(?<=[\.!?。！？])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _scan_markdown_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.md") if p.is_file())
