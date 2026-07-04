"""Tests for the heading-aware chunker."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.rag.chunker import chunk_document, estimate_tokens
from rdos.rag.markdown_parser import parse_markdown_text
from rdos.schemas.privacy import PrivacyLevel


def _make_doc(text: str, file_path: str = "x.md"):
    return parse_markdown_text(text, file_path=file_path)


def test_chunk_basic_single_heading() -> None:
    body = "# Title\n\n" + ("paragraph text. " * 30)
    meta, _ = _make_doc("# meta ignored\n\n" + body, file_path="x.md")
    chunks = chunk_document(meta, body)
    assert len(chunks) >= 1
    assert all(c.heading_path == ["Title"] for c in chunks)


def test_chunk_preserves_heading_path_nested() -> None:
    body = "\n".join(
        [
            "# Root",
            "",
            "intro",
            "",
            "## Child",
            "",
            "more text " * 60,
            "",
            "### Grandchild",
            "",
            "deep text " * 60,
        ]
    )
    meta, _ = _make_doc(body, file_path="nested.md")
    chunks = chunk_document(meta, body)
    paths = [c.heading_path for c in chunks]
    assert ["Root"] in paths
    assert ["Root", "Child"] in paths
    assert ["Root", "Child", "Grandchild"] in paths


def test_chunk_hash_is_stable_and_distinguishes_content() -> None:
    body_a = "# Title\n\nalpha beta gamma.\n"
    body_b = "# Title\n\ndelta epsilon zeta.\n"
    meta_a, _ = _make_doc(body_a, file_path="a.md")
    meta_b, _ = _make_doc(body_b, file_path="b.md")
    ca = chunk_document(meta_a, body_a)[0]
    cb = chunk_document(meta_b, body_b)[0]
    same = chunk_document(meta_a, body_a)[0]
    assert ca.chunk_hash == same.chunk_hash
    assert ca.chunk_hash != cb.chunk_hash


def test_chunk_id_stable_for_same_content() -> None:
    body = "# Title\n\nstable body line that repeats.\n"
    meta, _ = _make_doc(body, file_path="a.md")
    a = chunk_document(meta, body)[0]
    b = chunk_document(meta, body)[0]
    assert a.chunk_id == b.chunk_id


def test_chunk_respects_max_token_budget() -> None:
    # 40 paragraphs of ~50 tokens each → multiple chunks under default 600
    paragraphs = "\n\n".join(f"paragraph {i}: " + ("word " * 50) for i in range(40))
    body = "# Big\n\n" + paragraphs
    meta, _ = _make_doc(body, file_path="big.md")
    chunks = chunk_document(meta, body, target_min_tokens=100, target_max_tokens=200)
    assert len(chunks) >= 2
    # Each chunk (except possibly the last) should not blow past max too far
    assert all(c.token_count <= 260 for c in chunks)


def test_chunk_propagates_privacy_and_tags() -> None:
    text = """---
title: Tagged Note
tags: [a, b]
privacy_level: private_summary
---

# Heading

body
"""
    meta, _ = _make_doc(text, file_path="tagged.md")
    chunks = chunk_document(meta, text.split("---\n", 1)[1].split("---\n", 1)[1] if "---" in text else "")
    # body above includes frontmatter; we explicitly pass body without fm
    body = "# Heading\n\nbody\n"
    chunks = chunk_document(meta, body)
    assert chunks
    assert all(c.privacy_level == PrivacyLevel.private_summary for c in chunks)
    assert all(set(c.tags) == {"a", "b"} for c in chunks)


def test_chunk_token_estimator_variants() -> None:
    assert estimate_tokens("abcd", mode="char4") == 1
    assert estimate_tokens("abcd", mode="char3") == 1
    assert estimate_tokens("a b c d", mode="words") == 4


def test_chunk_skip_empty_section() -> None:
    body = "# H\n\n# H2\n\nreal text.\n"
    meta, _ = _make_doc(body, file_path="x.md")
    chunks = chunk_document(meta, body)
    assert all(c.chunk_text.strip() for c in chunks)


@pytest.fixture()
def _tmp_markdown(tmp_path: Path) -> Path:
    p = tmp_path / "note.md"
    p.write_text("# Title\n\nbody\n")
    return p
