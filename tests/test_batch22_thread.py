"""Tests for Batch 22: multi-turn research thread."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.threads.models import ThreadState, TurnRecord
from rdos.threads.rewriter import (
    context_for_new_turn,
    maybe_compress,
    rewrite_followup,
)
from rdos.threads.store import ThreadStore, add_turn


@pytest.fixture()
def store(tmp_path: Path) -> ThreadStore:
    return ThreadStore(tmp_path / "threads.db")


def _make_turn(index: int, q: str, a: str = "x", cids: list[str] | None = None) -> TurnRecord:
    return TurnRecord(
        turn_index=index,
        run_id=f"r{index}",
        question=q,
        answer=a,
        citation_chunk_ids=cids or [],
        timestamp=f"2026-07-05T00:00:0{index}Z",
    )


def test_thread_create_persists(store: ThreadStore) -> None:
    state = store.create(source_collection="clawd-research", privacy_level="private_raw")
    assert state.thread_id
    fetched = store.get(state.thread_id)
    assert fetched is not None
    assert fetched.source_collection == "clawd-research"
    store.close()


def test_add_turn_appends_and_carries_forward_citations(store: ThreadStore) -> None:
    state = store.create()
    add_turn(
        store, state,
        run_id="r1", question="what is AgentTrace?",
        answer="...",
        citation_chunk_ids=["c1", "c2"],
    )
    add_turn(
        store, state,
        run_id="r2", question="tell me more",
        answer="...",
        citation_chunk_ids=["c2", "c3"],
    )
    refreshed = store.get(state.thread_id)
    assert refreshed is not None
    assert len(refreshed.turns) == 2
    assert refreshed.cited_chunks == ["c1", "c2", "c3"]
    store.close()


def test_close_thread_sets_closed_at(store: ThreadStore) -> None:
    state = store.create()
    closed = store.close_thread(state.thread_id)
    assert closed is not None
    assert closed.closed_at is not None
    store.close()


def test_list_recent_returns_in_desc_order(store: ThreadStore) -> None:
    a = store.create()
    b = store.create()
    items = store.list_recent(limit=10)
    # Most recent first
    assert items[0].thread_id == b.thread_id
    assert items[1].thread_id == a.thread_id
    store.close()


# ---- followup rewriter ----


def test_rewrite_prepends_topic_for_pronoun_query() -> None:
    state = ThreadState(
        thread_id="t",
        created_at="2026-07-05T00:00:00Z",
        turns=[_make_turn(0, "What is AgentTrace?")],
    )
    rewritten = rewrite_followup(state, "它跟 flight recorder 有什麼關係？")
    assert rewritten.startswith("AgentTrace")
    assert "它" in rewritten


def test_rewrite_prepend_for_bare_modal() -> None:
    state = ThreadState(
        thread_id="t",
        created_at="2026-07-05T00:00:00Z",
        turns=[_make_turn(0, "What is GraphRAG?")],
    )
    rewritten = rewrite_followup(state, "可以舉例嗎？")
    assert "GraphRAG" in rewritten


def test_rewrite_no_change_when_topic_present() -> None:
    state = ThreadState(
        thread_id="t",
        created_at="2026-07-05T00:00:00Z",
        turns=[_make_turn(0, "What is GraphRAG?")],
    )
    rewritten = rewrite_followup(state, "GraphRAG 的核心方法是什麼？")
    assert rewritten == "GraphRAG 的核心方法是什麼？"


def test_rewrite_empty_history_returns_original() -> None:
    state = ThreadState(thread_id="t", created_at="2026-07-05T00:00:00Z")
    assert rewrite_followup(state, "hello") == "hello"


# ---- compression ----


def test_maybe_compress_triggers_when_turns_exceed_threshold() -> None:
    state = ThreadState(thread_id="t", created_at="2026-07-05T00:00:00Z")
    for i in range(7):
        state.turns.append(_make_turn(i, f"Q{i}", f"A{i}"))
    triggered = maybe_compress(state, max_turns=5)
    assert triggered is True
    assert state.compressed_summary
    # Most recent 5 turns are not in summary
    assert "Q5" not in state.compressed_summary
    assert "Q0" in state.compressed_summary


def test_maybe_compress_skips_when_summary_exists() -> None:
    state = ThreadState(
        thread_id="t", created_at="2026-07-05T00:00:00Z", compressed_summary="prior"
    )
    for i in range(7):
        state.turns.append(_make_turn(i, f"Q{i}"))
    triggered = maybe_compress(state, max_turns=5)
    assert triggered is False
    assert state.compressed_summary == "prior"


# ---- context_for_new_turn ----


def test_context_includes_recent_turns_and_carryforward() -> None:
    state = ThreadState(
        thread_id="t", created_at="2026-07-05T00:00:00Z",
        turns=[_make_turn(0, "Q0"), _make_turn(1, "Q1")],
        cited_chunks=["c1", "c2"],
    )
    ctx = context_for_new_turn(state, max_turns=5)
    assert len(ctx["prior_turns"]) == 2
    assert ctx["cited_chunk_ids"] == ["c1", "c2"]


def test_cli_wired() -> None:
    from rdos.cli.thread import app

    assert app is not None
