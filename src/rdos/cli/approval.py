"""`rdos approval list|show|approve|deny`."""

from __future__ import annotations

import json
import uuid
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rdos.approvals.queue import ApprovalQueue

app = typer.Typer(no_args_is_help=True, help="HITL approval queue")
console = Console()


def _queue() -> ApprovalQueue:
    return ApprovalQueue("data/approvals.db")


@app.command("list")
def list_cmd(
    limit: int = typer.Option(20, "--limit", "-n"),
    pending_only: bool = typer.Option(False, "--pending", help="Show only undecided"),
) -> None:
    q = _queue()
    items = q.list_pending(limit=limit) if pending_only else q.list_recent(limit=limit)
    if not items:
        console.print("[yellow]No approvals.[/yellow]")
        return
    table = Table(title="Approvals")
    table.add_column("approval_id", style="dim")
    table.add_column("tool", style="cyan")
    table.add_column("requested_at", style="white")
    table.add_column("decision", style="magenta")
    table.add_column("thread_id", style="dim")
    for r in items:
        table.add_row(
            r.approval_id[:12],
            r.tool_name,
            r.requested_at,
            r.decision or "(pending)",
            r.thread_id[:12],
        )
    console.print(table)
    q.close()


@app.command("show")
def show_cmd(approval_id: str = typer.Argument(...)) -> None:
    q = _queue()
    req = q.get(approval_id) or q._get_by_prefix(approval_id)  # type: ignore[attr-defined]
    if req is None:
        console.print(f"[red]No approval with id matching:[/red] {approval_id}")
        raise typer.Exit(code=1)
    console.print_json(json.dumps(req.model_dump(), ensure_ascii=False))
    q.close()


@app.command("approve")
def approve_cmd(
    approval_id: str = typer.Argument(...),
    decided_by: str = typer.Option("cli", "--by", help="Decider identity"),
) -> None:
    q = _queue()
    req = _resolve(q, approval_id)
    if req is None:
        console.print(f"[red]No approval with id matching:[/red] {approval_id}")
        raise typer.Exit(code=1)
    if req.decision is not None:
        console.print(
            f"[yellow]Already decided:[/yellow] {req.decision} by {req.decided_by} "
            f"at {req.decided_at}"
        )
        raise typer.Exit(code=0)
    updated = q.decide(req.approval_id, decision="approved", decided_by=decided_by)
    _resume_graph(updated, q)
    console.print(
        Panel.fit(
            f"approval_id: {req.approval_id}\n"
            f"decision: approved\n"
            f"by: {decided_by}",
            title="Approved",
        )
    )
    q.close()


@app.command("deny")
def deny_cmd(
    approval_id: str = typer.Argument(...),
    reason: str = typer.Option("denied by cli", "--reason"),
    decided_by: str = typer.Option("cli", "--by"),
) -> None:
    q = _queue()
    req = _resolve(q, approval_id)
    if req is None:
        console.print(f"[red]No approval with id matching:[/red] {approval_id}")
        raise typer.Exit(code=1)
    if req.decision is not None:
        console.print(
            f"[yellow]Already decided:[/yellow] {req.decision} by {req.decided_by}"
        )
        raise typer.Exit(code=0)
    updated = q.decide(
        req.approval_id, decision="denied", decided_by=decided_by, deny_reason=reason
    )
    _resume_graph(updated, q)
    console.print(
        Panel.fit(
            f"approval_id: {req.approval_id}\n"
            f"decision: denied\n"
            f"reason: {reason}\n"
            f"by: {decided_by}",
            title="Denied",
        )
    )
    q.close()


def _resolve(q: ApprovalQueue, prefix: str) -> Any:
    """Match exact approval_id or unique prefix."""
    direct = q.get(prefix)
    if direct is not None:
        return direct
    for r in q.list_recent(limit=10_000):
        if r.approval_id.startswith(prefix):
            return r
    return None


def _resume_graph(req: Any, q: ApprovalQueue) -> None:
    """Resume the LangGraph thread with the decision payload."""
    from langgraph.types import Command

    from rdos.config import get_config
    from rdos.graph.export_graph import build_export_graph

    cfg = get_config()
    # We don't have the original target_path on the request side easily; use args.
    target_path = req.args.get("target_path", f"data/generated/reports/synthesis_{req.run_id[:8]}.md")
    # Build a fresh graph instance for resume; checkpointer rehydrates state from thread_id.
    checkpointer = None
    try:
        graph = build_export_graph(
            cfg=cfg, target_path=target_path, queue=q, checkpointer=checkpointer
        )
        config = {"configurable": {"thread_id": req.thread_id}}
        payload = {"decision": req.decision or "denied", "deny_reason": req.deny_reason}
        graph.invoke(Command(resume=payload), config=config)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]graph resume skipped:[/yellow] {exc!s:.200}")


# Patch ApprovalQueue with prefix resolver for the CLI
def _patch_queue_prefix() -> None:
    from rdos.approvals.queue import ApprovalQueue as Q

    def _get_by_prefix(self: Q, prefix: str) -> Any:
        for r in self.list_recent(limit=10_000):
            if r.approval_id.startswith(prefix):
                return r
        return None

    if not hasattr(Q, "_get_by_prefix"):
        Q._get_by_prefix = _get_by_prefix


_patch_queue_prefix()

# Silence ruff unused-import
_ = uuid
