"""`rdos trace list` / `rdos trace show <run_id>` — read JSONL trace."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from rdos.config import get_config
from rdos.trace.trace_store import JsonlTraceStore

app = typer.Typer(no_args_is_help=True, help="Inspect run traces")
console = Console()


@app.command("list")
def list_cmd(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of recent runs"),
) -> None:
    cfg = get_config()
    store = JsonlTraceStore(_default_trace_path(cfg))
    runs = store.list_runs(limit=limit)
    if not runs:
        console.print("[yellow]No traces yet.[/yellow]")
        raise typer.Exit(code=0)

    table = Table(title="Recent runs")
    table.add_column("run_id", style="dim")
    table.add_column("timestamp", style="white")
    table.add_column("task_type", style="cyan")
    table.add_column("privacy", style="yellow")
    table.add_column("model", style="magenta")
    for r in runs:
        privacy = r.effective_privacy_level or "?"
        model = r.model_routing_decision.selected_profile if r.model_routing_decision else "?"
        table.add_row(
            r.run_id[:12],
            r.timestamp,
            r.task_type,
            privacy,
            model,
        )
    console.print(table)


@app.command("show")
def show_cmd(
    run_id: str = typer.Argument(..., help="Run id (or unique prefix)"),
) -> None:
    cfg = get_config()
    store = JsonlTraceStore(_default_trace_path(cfg))

    record = store.get(run_id)
    if record is None:
        # Try prefix match
        for r in store.list_runs(limit=10_000):
            if r.run_id.startswith(run_id):
                record = r
                break
    if record is None:
        console.print(f"[red]No trace with run_id matching:[/red] {run_id}")
        raise typer.Exit(code=1)

    console.print_json(json.dumps(record.model_dump(mode="json"), ensure_ascii=False))


def _default_trace_path(cfg) -> str:
    return "data/traces/runs.jsonl"
