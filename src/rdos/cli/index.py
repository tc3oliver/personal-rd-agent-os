"""`rdos index <path>` — index Markdown notes."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rdos.rag.indexer import index_directory

app = typer.Typer(no_args_is_help=True, help="Index Markdown notes into RDOS stores")
console = Console()


@app.callback(invoke_without_command=True)
def index_cmd(
    path: str = typer.Argument(..., help="Directory containing .md files"),
    reset: bool = typer.Option(False, "--reset", help="Drop LanceDB table before indexing"),
) -> None:
    """Scan PATH for .md files and index them."""
    if not Path(path).exists():
        console.print(f"[red]Path not found:[/red] {path}")
        raise typer.Exit(code=2)

    stats = index_directory(path, reset=reset)

    table = Table(title="Index Result")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Indexed documents", str(stats.documents_indexed))
    table.add_row("Generated chunks (new)", str(stats.chunks_inserted))
    table.add_row("Skipped (duplicate)", str(stats.chunks_skipped))
    table.add_row("SQLite path", stats.sqlite_path)
    table.add_row("LanceDB path", stats.lancedb_path)
    table.add_row("Elapsed (ms)", str(stats.elapsed_ms))
    console.print(table)
