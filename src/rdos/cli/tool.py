"""`rdos tool` — invoke / policy-check tools from the command line."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rdos.config import get_config
from rdos.rag.embedding import build_embedding_provider
from rdos.rag.retriever import HybridRetriever
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.privacy import PrivacyLevel
from rdos.tools.capability_boundary import CapabilityBoundary
from rdos.tools.knowledge_tools import (
    ListRecentNotesTool,
    ReadNoteTool,
    SearchNotesTool,
)
from rdos.tools.permission_gate import PermissionGate
from rdos.tools.registry import ToolRegistry

app = typer.Typer(no_args_is_help=True, help="Inspect and invoke runtime tools")
console = Console()


def _boundary(cfg) -> CapabilityBoundary:
    tool_rule = cfg.tool_policy.tools.get("read_note")
    allowed_roots = ["sample_data", "docs", "eval_sets", "data/reports"]
    max_bytes = 2 * 1024 * 1024
    if tool_rule is not None:
        # Future: pull allowed_roots / max_bytes from policy when we extend schema.
        pass
    return CapabilityBoundary(allowed_roots=allowed_roots, max_bytes=max_bytes)


def _registry(cfg) -> ToolRegistry:
    boundary = _boundary(cfg)
    registry = ToolRegistry(cfg.tool_policy, boundary)

    dim = cfg.models.embedding.dim or cfg.rag.embedding.dim
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=dim)
    embedding = build_embedding_provider(
        cfg.models.embedding.provider, dim=dim
    )
    retriever = HybridRetriever(
        sqlite_store=store, vector_store=vectors, embedding=embedding, config=cfg
    )
    registry.register(SearchNotesTool(retriever))
    registry.register(ReadNoteTool())
    registry.register(ListRecentNotesTool(store))
    return registry


@app.command("policy-check")
def policy_check_cmd(
    tool_name: str = typer.Argument(..., help="Tool name to evaluate"),
    privacy: str = typer.Option("private_raw", "--privacy", help="Effective privacy level"),
    arg: list[str] = typer.Option(  # noqa: B008
        [], "--arg", help="Repeatable key=value kwargs (e.g. --arg path=foo.md)"
    ),
) -> None:
    """Show the permission decision for TOOL_NAME without executing it."""
    cfg = get_config()
    gate = PermissionGate(cfg.tool_policy)
    decision = gate.evaluate(tool_name, PrivacyLevel(privacy))

    boundary_result = None
    if "path" in [a.split("=", 1)[0] for a in arg if "=" in a]:
        kwargs = dict(a.split("=", 1) for a in arg if "=" in a)
        boundary_result = _boundary(cfg).check_read(kwargs["path"])

    table = Table(title=f"Policy check: {tool_name}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("tool", tool_name)
    table.add_row("privacy", privacy)
    table.add_row("allowed", str(decision.allowed))
    table.add_row("requires_approval", str(decision.requires_approval))
    table.add_row("reason", decision.reason)
    if boundary_result is not None:
        table.add_row("boundary.allowed", str(boundary_result.allowed))
        table.add_row("boundary.reason", boundary_result.reason)
        table.add_row("boundary.resolved", boundary_result.resolved_path)
    console.print(table)


@app.command("read-note")
def read_note_cmd(
    path: str = typer.Argument(..., help="Path to a note file"),
    privacy: str = typer.Option("private_raw", "--privacy", help="Effective privacy level"),
) -> None:
    """Read a note through the tool registry (subject to policy + boundary)."""
    cfg = get_config()
    registry = _registry(cfg)
    invocation = registry.invoke("read_note", privacy, path=path)
    if invocation.decision.requires_approval:
        console.print(
            f"[yellow]approval_required:[/yellow] {invocation.decision.reason}"
        )
        raise typer.Exit(code=10)
    if not invocation.decision.allowed:
        console.print(f"[red]denied:[/red] {invocation.decision.reason}")
        raise typer.Exit(code=3)
    if invocation.boundary and not invocation.boundary.allowed:
        console.print(f"[red]boundary denied:[/red] {invocation.boundary.reason}")
        raise typer.Exit(code=4)
    if not invocation.output:
        console.print("[red]no output[/red]")
        raise typer.Exit(code=1)
    payload = invocation.output
    console.print(
        f"[cyan]read {payload['size']} bytes from[/cyan] {payload['path']}"
    )
    console.print(payload["content"])


@app.command("list")
def list_cmd() -> None:
    """List registered tools."""
    cfg = get_config()
    registry = _registry(cfg)
    table = Table(title="Registered tools")
    table.add_column("name", style="cyan")
    table.add_column("description", style="white")
    for name in registry.names():
        tool = registry.get(name)
        table.add_row(name, getattr(tool, "description", ""))
    console.print(table)


@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search query"),
    privacy: str = typer.Option("private_raw", "--privacy", help="Effective privacy level"),
    top_k: int = typer.Option(5, "--top-k", help="Top K"),
) -> None:
    """Invoke search_notes through the registry."""
    cfg = get_config()
    registry = _registry(cfg)
    invocation = registry.invoke("search_notes", privacy, query=query, top_k=top_k)
    if not invocation.decision.allowed:
        console.print(f"[red]denied:[/red] {invocation.decision.reason}")
        raise typer.Exit(code=3)
    console.print_json(json.dumps(invocation.output or {}, ensure_ascii=False))


# Silence ruff unused-import for Path
_ = Path
