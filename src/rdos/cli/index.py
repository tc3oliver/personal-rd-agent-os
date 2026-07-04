"""`rdos index <path>` — index Markdown notes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rdos.rag.indexer import index_directory
from rdos.schemas.privacy import PrivacyLevel

app = typer.Typer(no_args_is_help=True, help="Index Markdown notes into RDOS stores")
console = Console()


@app.callback(invoke_without_command=True)
def index_cmd(
    path: str = typer.Argument(..., help="Directory containing .md files"),
    reset: bool = typer.Option(False, "--reset", help="Drop LanceDB table before indexing"),
    embedding_provider: str = typer.Option(
        None,
        "--embedding-provider",
        help="fake | local-bge-m3 (default: from config)",
    ),
    source_collection: str | None = typer.Option(
        None,
        "--source-collection",
        help="Tag indexed docs with this source_collection",
    ),
    privacy_default: str = typer.Option(
        "private_raw",
        "--privacy-default",
        help="Default privacy level for files missing frontmatter",
    ),
    report: bool = typer.Option(
        False,
        "--report",
        help="Write data/reports/index_report_<timestamp>.md",
    ),
) -> None:
    """Scan PATH for .md files and index them."""
    if not Path(path).exists():
        console.print(f"[red]Path not found:[/red] {path}")
        raise typer.Exit(code=2)

    report_path: str | None = None
    if report:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        report_path = f"data/reports/index_report_{timestamp}.md"

    stats = index_directory(
        path,
        reset=reset,
        embedding_provider=embedding_provider,
        source_collection=source_collection,
        privacy_default=PrivacyLevel(privacy_default),
        report_path=report_path,
    )

    table = Table(title="Index Result")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Documents indexed", str(stats.documents_indexed))
    table.add_row("Documents created", str(stats.documents_created))
    table.add_row("Documents updated", str(stats.documents_updated))
    table.add_row("Documents unchanged", str(stats.documents_unchanged))
    table.add_row("Documents stale", str(stats.documents_stale))
    table.add_row("Generated chunks (new)", str(stats.chunks_inserted))
    table.add_row("Skipped (duplicate)", str(stats.chunks_skipped))
    table.add_row("SQLite path", stats.sqlite_path)
    table.add_row("LanceDB path", stats.lancedb_path)
    table.add_row("Source collection", stats.source_collection or "-")
    table.add_row("Embedding provider", stats.embedding_provider or "?")
    table.add_row("Embedding model", stats.embedding_model or "?")
    table.add_row("Embedding dim", str(stats.embedding_dim or "?"))
    table.add_row("Elapsed (ms)", str(stats.elapsed_ms))
    console.print(table)
    if report_path:
        console.print(f"Report written to [cyan]{report_path}[/cyan]")
