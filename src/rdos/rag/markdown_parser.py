"""Markdown parser with YAML frontmatter support.

Parses a Markdown note into a `DocumentMetadata` + body text. Does NOT
split chunks (see `chunker.py`). Heading tree extraction is shared
between parser and chunker.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import frontmatter

from rdos.schemas.document import DocumentMetadata
from rdos.schemas.privacy import PrivacyLevel

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _parse_privacy_level(raw: object, default: PrivacyLevel) -> PrivacyLevel:
    if raw is None:
        return default
    if isinstance(raw, str):
        try:
            return PrivacyLevel(raw.strip().lower())
        except ValueError:
            return default
    return default


def _compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_doc_id(file_path: Path, content_hash: str) -> str:
    rel = str(file_path).encode("utf-8")
    return hashlib.sha1(rel + b"|" + content_hash.encode("utf-8")).hexdigest()[:16]


def _ensure_tags_list(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    if isinstance(raw, list | tuple):
        return [str(t).strip() for t in raw if str(t).strip()]
    return []


def parse_markdown_text(text: str, file_path: str = "<inline>") -> tuple[DocumentMetadata, str]:
    """Parse Markdown text into (DocumentMetadata, body).

    Body is the Markdown minus the frontmatter. Headings are NOT split here.
    """
    post = frontmatter.loads(text)
    meta = post.metadata
    body = post.content

    title = str(meta.get("title") or "").strip() or Path(file_path).stem
    date = str(meta.get("date") or "").strip() or None
    tags = _ensure_tags_list(meta.get("tags"))
    privacy = _parse_privacy_level(
        meta.get("privacy_level"),
        default=PrivacyLevel.private_raw,
    )
    content_hash = _compute_content_hash(body)
    doc_id = _stable_doc_id(Path(file_path), content_hash)

    return (
        DocumentMetadata(
            doc_id=doc_id,
            file_path=file_path,
            title=title,
            date=date,
            tags=tags,
            privacy_level=privacy,
            content_hash=content_hash,
        ),
        body,
    )


def parse_markdown_file(path: str | Path) -> tuple[DocumentMetadata, str]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return parse_markdown_text(text, file_path=str(p))


def extract_heading_tree(body: str) -> list[tuple[int, str]]:
    """Return a list of (level, text) for every heading in the body."""
    out: list[tuple[int, str]] = []
    for line in body.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def render_markdown_for_chunk(text: str) -> str:
    """Render markdown to plain text (no HTML tags). Used for chunk_text estimation."""
    from markdown_it import MarkdownIt

    md = MarkdownIt("commonmark", {"html": False})
    tokens = md.parse(text, {})
    parts: list[str] = []
    for tok in tokens:
        if tok.type in ("paragraph_open", "paragraph_close", "heading_open", "heading_close"):
            continue
        if tok.type == "inline" or tok.type in ("fence", "code_block"):
            parts.append(tok.content)
    return "\n".join(parts).strip()
