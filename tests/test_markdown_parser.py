"""Tests for markdown_parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.rag.markdown_parser import (
    extract_heading_tree,
    parse_markdown_text,
)
from rdos.schemas.privacy import PrivacyLevel


def test_parses_frontmatter_title() -> None:
    text = """---
title: Hello World
date: 2026-07-05
tags: [rag, retrieval]
privacy_level: public
---

# Section

Body text here.
"""
    meta, body = parse_markdown_text(text, file_path="hello.md")
    assert meta.title == "Hello World"
    assert meta.date == "2026-07-05"
    assert meta.tags == ["rag", "retrieval"]
    assert meta.privacy_level == PrivacyLevel.public
    assert "Section" in body
    assert meta.doc_id  # non-empty


def test_default_privacy_when_missing() -> None:
    text = """---
title: No Privacy
---

# Heading

text
"""
    meta, _ = parse_markdown_text(text, file_path="x.md")
    assert meta.privacy_level == PrivacyLevel.private_raw


def test_invalid_privacy_falls_back_to_default() -> None:
    text = """---
title: Bad
privacy_level: top_secret
---

body
"""
    meta, _ = parse_markdown_text(text, file_path="x.md")
    assert meta.privacy_level == PrivacyLevel.private_raw


def test_title_falls_back_to_filename_when_missing() -> None:
    # Batch 12: H1 takes priority over filename; title only falls back to
    # filename when BOTH frontmatter and H1 are missing.
    text = """---
date: 2026-07-05
---

# Heading

text
"""
    meta, _ = parse_markdown_text(text, file_path="my-note.md")
    assert meta.title == "Heading"


def test_title_falls_back_to_filename_only_when_no_h1() -> None:
    meta, _ = parse_markdown_text("no heading here", file_path="my-note.md")
    assert meta.title == "my-note"


def test_tags_accept_comma_string() -> None:
    text = """---
title: x
tags: a, b, c
---

body
"""
    meta, _ = parse_markdown_text(text, file_path="x.md")
    assert meta.tags == ["a", "b", "c"]


def test_content_hash_stable() -> None:
    text = """---
title: x
---

# Heading

body line.
"""
    a, _ = parse_markdown_text(text, file_path="x.md")
    b, _ = parse_markdown_text(text, file_path="x.md")
    assert a.content_hash == b.content_hash
    # Same content → same doc_id even with different path
    other, _ = parse_markdown_text(text, file_path="y.md")
    assert a.content_hash == other.content_hash


def test_heading_tree_levels() -> None:
    body = """# A

text

## A1

text

### A1a

text

## A2

text
"""
    tree = extract_heading_tree(body)
    assert tree == [(1, "A"), (2, "A1"), (3, "A1a"), (2, "A2")]


def test_parses_sample_data_notes(sample_notes_dir: Path) -> None:
    files = sorted(sample_notes_dir.glob("*.md"))
    assert len(files) >= 5, "expected at least 5 synthetic notes"
    for f in files:
        meta, body = parse_markdown_text(f.read_text(encoding="utf-8"), file_path=str(f))
        assert meta.title
        assert body.strip()


@pytest.fixture()
def sample_notes_dir() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "sample_data" / "notes"
