"""Tests for Batch 19: HITL approval runtime."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.approvals.models import ApprovalRequest
from rdos.approvals.queue import ApprovalQueue


def _make_queue(tmp_path: Path) -> ApprovalQueue:
    return ApprovalQueue(tmp_path / "approvals.db")


def test_request_creates_unique_approval(tmp_path: Path) -> None:
    q = _make_queue(tmp_path)
    req, created = q.request(
        run_id="r1",
        thread_id="t1",
        tool_name="export_report",
        args={"target_path": "out.md", "content": "x"},
    )
    assert created is True
    assert req.approval_id
    assert req.idempotency_key
    assert req.decision is None
    q.close()


def test_request_is_idempotent_on_same_args(tmp_path: Path) -> None:
    q = _make_queue(tmp_path)
    args = {"target_path": "out.md", "content": "x"}
    req1, created1 = q.request(
        run_id="r1", thread_id="t1", tool_name="export_report", args=args
    )
    req2, created2 = q.request(
        run_id="r1", thread_id="t1", tool_name="export_report", args=args
    )
    assert created1 is True
    assert created2 is False
    assert req1.approval_id == req2.approval_id
    q.close()


def test_request_different_args_creates_new_approval(tmp_path: Path) -> None:
    q = _make_queue(tmp_path)
    req1, _ = q.request(
        run_id="r1", thread_id="t1", tool_name="export_report",
        args={"target_path": "a.md", "content": "x"},
    )
    req2, _ = q.request(
        run_id="r1", thread_id="t1", tool_name="export_report",
        args={"target_path": "b.md", "content": "x"},
    )
    assert req1.approval_id != req2.approval_id
    q.close()


def test_decide_approve_sets_decision(tmp_path: Path) -> None:
    q = _make_queue(tmp_path)
    req, _ = q.request(
        run_id="r1", thread_id="t1", tool_name="export_report",
        args={"target_path": "out.md", "content": "x"},
    )
    decided = q.decide(req.approval_id, decision="approved", decided_by="alice")
    assert decided is not None
    assert decided.decision == "approved"
    assert decided.decided_by == "alice"
    assert decided.decided_at is not None
    q.close()


def test_decide_deny_records_reason(tmp_path: Path) -> None:
    q = _make_queue(tmp_path)
    req, _ = q.request(
        run_id="r1", thread_id="t1", tool_name="export_report",
        args={"target_path": "out.md", "content": "x"},
    )
    decided = q.decide(
        req.approval_id, decision="denied", decided_by="bob", deny_reason="off-topic"
    )
    assert decided.decision == "denied"
    assert decided.deny_reason == "off-topic"
    q.close()


def test_decide_is_immutable(tmp_path: Path) -> None:
    q = _make_queue(tmp_path)
    req, _ = q.request(
        run_id="r1", thread_id="t1", tool_name="export_report",
        args={"target_path": "out.md", "content": "x"},
    )
    q.decide(req.approval_id, decision="approved", decided_by="alice")
    # Try to flip
    again = q.decide(req.approval_id, decision="denied", decided_by="mallory")
    assert again.decision == "approved"  # original decision sticks
    assert again.decided_by == "alice"
    q.close()


def test_decide_invalid_value_raises(tmp_path: Path) -> None:
    q = _make_queue(tmp_path)
    req, _ = q.request(
        run_id="r1", thread_id="t1", tool_name="export_report",
        args={"target_path": "out.md", "content": "x"},
    )
    with pytest.raises(ValueError):
        q.decide(req.approval_id, decision="maybe")
    q.close()


def test_list_pending_filters_undecided(tmp_path: Path) -> None:
    q = _make_queue(tmp_path)
    r1, _ = q.request(
        run_id="r1", thread_id="t1", tool_name="export_report",
        args={"target_path": "a.md", "content": "x"},
    )
    r2, _ = q.request(
        run_id="r2", thread_id="t2", tool_name="export_report",
        args={"target_path": "b.md", "content": "y"},
    )
    q.decide(r1.approval_id, decision="approved")
    pending = q.list_pending()
    assert {p.approval_id for p in pending} == {r2.approval_id}
    q.close()


def test_mark_executed_increments_replay_count(tmp_path: Path) -> None:
    q = _make_queue(tmp_path)
    req, _ = q.request(
        run_id="r1", thread_id="t1", tool_name="export_report",
        args={"target_path": "out.md", "content": "x"},
    )
    q.mark_executed(req.approval_id)
    q.mark_executed(req.approval_id)
    fetched = q.get(req.approval_id)
    assert fetched is not None
    assert fetched.replay_count == 2
    q.close()


def test_get_by_key_finds_existing(tmp_path: Path) -> None:
    q = _make_queue(tmp_path)
    req, _ = q.request(
        run_id="r1", thread_id="t1", tool_name="export_report",
        args={"target_path": "out.md", "content": "x"},
    )
    found = q.get_by_key(req.idempotency_key)
    assert found is not None
    assert found.approval_id == req.approval_id
    q.close()


def test_models_roundtrip() -> None:
    """ApprovalRequest survives model_dump → model_validate."""
    req = ApprovalRequest(
        approval_id="a",
        run_id="r",
        thread_id="t",
        tool_name="export_report",
        args={"x": 1},
        requested_at="2026-07-05T00:00:00Z",
        idempotency_key="k",
    )
    dumped = req.model_dump()
    restored = ApprovalRequest(**dumped)
    assert restored == req


def test_cli_wired() -> None:
    from rdos.cli.approval import app

    assert app is not None


# ---- export_graph integration (offline, no live synthesis) ----


def test_export_graph_synthesize_to_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: synthesize → request → interrupt → resume → write."""
    monkeypatch.chdir(tmp_path)
    # Use the sample_data corpus for a deterministic test
    here = Path(__file__).resolve().parent
    sample_notes = here.parent / "sample_data" / "notes"

    from rdos.config import (
        ChunkingConfig,
        EmbeddingConfig,
        EmbeddingRuntimeConfig,
        ModelsConfig,
        PrivacyPolicyConfig,
        PrivacyRule,
        ProfileConfig,
        RagConfig,
        RdosConfig,
        RetrievalConfig,
        StorageConfig,
    )
    from rdos.rag.indexer import index_directory

    cfg = RdosConfig(
        models=ModelsConfig(
            profiles={"local_fast": ProfileConfig(provider="local", model="stub")},
            task_defaults={"research_memory": "local_fast"},
            embedding=EmbeddingConfig(provider="fake", dim=32),
        ),
        privacy_policy=PrivacyPolicyConfig(
            privacy_order=["public", "private_summary", "private_raw", "company_sensitive"],
            default_chunk_privacy="private_raw",
            default_query_privacy="private_raw",
            rules={
                lv: PrivacyRule(allow_external_model=False, requires_user_confirmation=False)
                for lv in ("public", "private_summary", "private_raw", "company_sensitive")
            },
        ),
        rag=RagConfig(
            chunking=ChunkingConfig(target_min_tokens=30, target_max_tokens=120),
            storage=StorageConfig(
                sqlite_path=str(tmp_path / "rdos.db"),
                lancedb_path=str(tmp_path / "lancedb"),
            ),
            embedding=EmbeddingRuntimeConfig(dim=32),
            retrieval=RetrievalConfig(top_k=3, enable_query_rewrite=False),
        ),
    )
    index_directory(sample_notes, config=cfg)

    from rdos.approvals.queue import ApprovalQueue
    from rdos.graph.export_graph import build_export_graph, build_sqlite_checkpointer

    queue = ApprovalQueue(tmp_path / "approvals.db")
    cp = build_sqlite_checkpointer(str(tmp_path / "checkpoints.db"))
    target = tmp_path / "out" / "report.md"
    graph = build_export_graph(
        cfg=cfg, target_path=str(target), queue=queue, checkpointer=cp
    )

    thread_id = "t-test-1"
    config = {"configurable": {"thread_id": thread_id}}
    # First invoke should hit interrupt at request_approval.
    state = graph.invoke(
        {"question": "RAG filtering", "run_id": "r1", "thread_id": thread_id},
        config=config,
    )
    # The graph pauses at interrupt — check approvals table has a pending entry.
    pending = queue.list_pending()
    assert len(pending) >= 1
    approval_id = pending[0].approval_id
    queue.decide(approval_id, decision="approved")

    # Resume
    from langgraph.types import Command

    state = graph.invoke(
        Command(resume={"decision": "approved"}), config=config
    )
    assert state.get("approval_decision") == "approved"
    # The file should have been written.
    assert target.exists()
    # Replay protection at the queue level: mark_executed twice increments counter.
    # LangGraph won't re-run write_or_skip on a thread already at END, so we test
    # replay protection directly via queue.mark_executed in test_mark_executed_increments_replay_count.
    fetched = queue.get(approval_id)
    assert fetched is not None
    assert fetched.replay_count >= 1
    queue.close()
