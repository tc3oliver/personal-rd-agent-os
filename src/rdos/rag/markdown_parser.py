"""Markdown parser with YAML frontmatter support.

Parses a Markdown note into a `DocumentMetadata` + body text. Does NOT
split chunks (see `chunker.py`). Heading tree extraction is shared
between parser and chunker.

Batch 12 additions:
- source_collection propagation
- topic derived from folder name
- title fallback: H1 → filename stem (not just stem)
- date fallback: frontmatter → filename YYMMDD prefix → None
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import frontmatter

from rdos.schemas.document import DocumentMetadata
from rdos.schemas.privacy import PrivacyLevel

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_DATE_PREFIX_RE = re.compile(r"^(\d{6})")
_H1_RE = re.compile(r"^#\s+(.+?)\s*#*\s*$")


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


def _filename_to_date(filename: str) -> str | None:
    """Try YYMMDD prefix → YYYY-MM-DD."""
    stem = Path(filename).stem
    m = _DATE_PREFIX_RE.match(stem)
    if not m:
        return None
    yy, mm, dd = m.group(1)[:2], m.group(1)[2:4], m.group(1)[4:6]
    year = 2000 + int(yy)
    if 1 <= int(mm) <= 12 and 1 <= int(dd) <= 31:
        return f"{year:04d}-{mm}-{dd}"
    return None


def _filename_title(filename: str) -> str:
    stem = Path(filename).stem
    m = _DATE_PREFIX_RE.match(stem)
    if m:
        rest = stem[m.end():].lstrip("_- ")
        return rest or stem
    return stem


def _h1_from_body(body: str) -> str | None:
    for line in body.splitlines():
        m = _H1_RE.match(line)
        if m:
            return m.group(1).strip()
    return None


def parse_markdown_text(
    text: str,
    file_path: str = "<inline>",
    *,
    source_collection: str | None = None,
    topic: str | None = None,
    privacy_default: PrivacyLevel = PrivacyLevel.private_raw,
) -> tuple[DocumentMetadata, str]:
    """Parse Markdown text into (DocumentMetadata, body).

    `source_collection` and `topic` are propagated as-is; if absent,
    they remain empty strings on the metadata object.
    """
    post = frontmatter.loads(text)
    meta = post.metadata
    body = post.content

    title_raw = str(meta.get("title") or "").strip()
    title = title_raw if title_raw else _h1_from_body(body) or _filename_title(file_path)
    date = str(meta.get("date") or "").strip() or _filename_to_date(file_path)
    tags = _ensure_tags_list(meta.get("tags"))
    privacy = _parse_privacy_level(
        meta.get("privacy_level"),
        default=privacy_default,
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
            source_collection=source_collection or "",
            topic=topic or "",
        ),
        body,
    )


def parse_markdown_file(
    path: str | Path,
    *,
    source_collection: str | None = None,
    topic: str | None = None,
    privacy_default: PrivacyLevel = PrivacyLevel.private_raw,
) -> tuple[DocumentMetadata, str]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return parse_markdown_text(
        text,
        file_path=str(p),
        source_collection=source_collection,
        topic=topic,
        privacy_default=privacy_default,
    )


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


def derive_topic_from_path(file_path: str | Path, root: str | Path | None) -> str:
    """Topic = first folder name under root, or top-level folder name."""
    fp = Path(file_path)
    if root is not None:
        try:
            rel = fp.relative_to(root)
            parts = rel.parts
            if len(parts) >= 2 and parts[-1]:  # file is in a subfolder
                return parts[0]
        except ValueError:
            pass
    parents = [p for p in fp.parts if p and p not in (".", "/")]
    return parents[-2] if len(parents) >= 2 else ""
