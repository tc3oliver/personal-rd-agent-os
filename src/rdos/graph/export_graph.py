"""Export graph — produces a synthesis then triggers HITL approval before write.

Workflow:
  1. synthesize  — run research synthesis, capture claims + citations
  2. request_approval — interrupt() with the export args; resume after approval
  3. write_or_skip — on resume: if approved, write the file; if denied, record reason

The graph uses a SQLite checkpointer so an approved/denied decision can resume
the thread days later.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from rdos.approvals.queue import ApprovalQueue
from rdos.apps.synthesize import run_synthesis
from rdos.config import RdosConfig
from rdos.llm.provider import LLMAdapter, StubLLMAdapter
from rdos.tools.export_tools import ExportReportTool


class ExportGraphState(TypedDict, total=False):
    question: str
    target_path: str
    run_id: str
    thread_id: str
    approval_id: str
    approval_decision: str
    deny_reason: str
    synthesis_md: str
    synthesis_path: str
    written_path: str
    skipped_reason: str
    error: str


def _synthesize(state: ExportGraphState, *, cfg: RdosConfig, llm: LLMAdapter) -> dict[str, Any]:
    out, md_path = run_synthesis(
        cfg=cfg,
        question=state["question"],
        embedding_provider=None,
        llm=llm,
    )
    # Read the actual markdown content so export_report writes content,
    # not the file path. (Validation A found this was writing the path.)
    from pathlib import Path

    md_content = Path(md_path).read_text(encoding="utf-8") if Path(md_path).exists() else ""
    return {"synthesis_md": md_content, "synthesis_path": md_path}


def _make_request(
    state: ExportGraphState,
    *,
    queue: ApprovalQueue,
    target_path: str,
) -> dict[str, Any]:
    args = {
        "target_path": target_path,
        "content": state.get("synthesis_md", ""),
        "format": "markdown",
    }
    req, _created = queue.request(
        run_id=state["run_id"],
        thread_id=state["thread_id"],
        tool_name="export_report",
        args=args,
    )
    # interrupt pauses here. On resume, the value returned from interrupt()
    # is what the caller passes to Command(resume=...).
    decision_payload = interrupt(
        {
            "approval_id": req.approval_id,
            "tool": "export_report",
            "target_path": target_path,
            "thread_id": req.thread_id,
        }
    )
    return {
        "approval_id": req.approval_id,
        "approval_decision": decision_payload.get("decision", "denied"),
        "deny_reason": decision_payload.get("deny_reason"),
    }


def _write_or_skip(state: ExportGraphState, *, queue: ApprovalQueue) -> dict[str, Any]:
    if state.get("approval_decision") != "approved":
        queue.mark_executed(state["approval_id"])
        return {"skipped_reason": "denied"}
    # Replay protection — only execute once per approval_id.
    existing = queue.get(state["approval_id"])
    if existing and existing.replay_count >= 1:
        return {"skipped_reason": "replay_blocked"}
    tool = ExportReportTool()
    args_payload = existing.args if existing else {}
    out = tool.run(
        target_path=args_payload.get("target_path", state.get("target_path", "")),
        content=args_payload.get("content", state.get("synthesis_md", "")),
        format=args_payload.get("format", "markdown"),
    )
    queue.mark_executed(state["approval_id"])
    return {"written_path": out["path"]}


def build_export_graph(
    *,
    cfg: RdosConfig,
    target_path: str,
    queue: ApprovalQueue,
    checkpointer: SqliteSaver | None = None,
    llm: LLMAdapter | None = None,
):
    """Build and compile the export graph."""
    used_llm = llm or StubLLMAdapter()

    def s_synthesize(state: ExportGraphState) -> dict[str, Any]:
        return _synthesize(state, cfg=cfg, llm=used_llm)

    def s_request(state: ExportGraphState) -> dict[str, Any]:
        return _make_request(state, queue=queue, target_path=target_path)

    def s_write(state: ExportGraphState) -> dict[str, Any]:
        return _write_or_skip(state, queue=queue)

    builder = StateGraph(ExportGraphState)
    builder.add_node("synthesize", s_synthesize)
    builder.add_node("request_approval", s_request)
    builder.add_node("write_or_skip", s_write)
    builder.add_edge(START, "synthesize")
    builder.add_edge("synthesize", "request_approval")
    builder.add_edge("request_approval", "write_or_skip")
    builder.add_edge("write_or_skip", END)

    cp = checkpointer or build_sqlite_checkpointer()
    return builder.compile(checkpointer=cp)


def build_sqlite_checkpointer(path: str = "data/checkpoints.db") -> SqliteSaver:
    from rdos.graph.checkpointer import build_sqlite_checkpointer as _b

    return _b(path)


def _silence(_: Any) -> None:
    return None
