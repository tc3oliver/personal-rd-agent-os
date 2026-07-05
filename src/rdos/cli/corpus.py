"""`rdos index-corpus <corpus> --scope <scope>` — preset ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rdos.config import get_config
from rdos.rag.corpus_presets import CORPUS_PRESETS, get_preset, resolve_corpus_root
from rdos.rag.indexer import index_directory
from rdos.schemas.privacy import PrivacyLevel

app = typer.Typer(no_args_is_help=True, help="Index corpus presets")
console = Console()


@app.callback(invoke_without_command=True)
def index_corpus_cmd(
    corpus: str = typer.Argument(..., help="Corpus name (e.g. research-notes)"),
    scope: str = typer.Option("all", "--scope", help="Preset scope"),
    embedding_provider: str = typer.Option(
        None, "--embedding-provider", help="fake | local-bge-m3"
    ),
    privacy_default: str = typer.Option(
        "private_raw", "--privacy-default", help="Default privacy for missing frontmatter"
    ),
    reset: bool = typer.Option(False, "--reset", help="Drop LanceDB table before indexing"),
) -> None:
    """Index a corpus scope (incremental)."""
    if corpus not in CORPUS_PRESETS:
        console.print(
            f"[red]Unknown corpus:[/red] {corpus}. "
            f"Known: {sorted(CORPUS_PRESETS)}"
        )
        raise typer.Exit(code=2)

    preset = get_preset(corpus, scope)
    root = Path(resolve_corpus_root(corpus))
    if not root.exists():
        console.print(f"[red]Corpus root not found:[/red] {root}")
        raise typer.Exit(code=2)

    if preset.folders:
        scan_paths = [root / folder for folder in preset.folders]
        scan_paths = [p for p in scan_paths if p.exists()]
        if not scan_paths:
            console.print(
                f"[red]No matching folders under[/red] {root} "
                f"for scope {scope!r} (looked for {preset.folders})"
            )
            raise typer.Exit(code=2)
    else:
        scan_paths = [root]

    console.print(
        f"[cyan]Indexing[/cyan] corpus={corpus} scope={scope} "
        f"({preset.description})"
    )
    console.print(f"  root: {root}")
    console.print(f"  paths: {[str(p) for p in scan_paths]}")

    cfg = get_config()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = Path(cfg.rag.storage.sqlite_path).parent.parent / "reports" / f"index_report_{corpus}_{scope}_{timestamp}.md"
    stats_total = None

    for sp in scan_paths:
        stats = index_directory(
            sp,
            config=cfg,
            embedding_provider=embedding_provider,
            reset=reset and sp is scan_paths[0],
            source_collection=corpus,
            privacy_default=PrivacyLevel(privacy_default),
            report_path=None,  # write a single combined report at the end
        )
        stats_total = stats if stats_total is None else stats_total
        # Show per-folder mini table
        mini = Table(title=f"Scope {scope} ← {sp.name}")
        mini.add_column("Metric", style="cyan")
        mini.add_column("Value", style="white")
        mini.add_row("documents indexed", str(stats.documents_indexed))
        mini.add_row("chunks inserted", str(stats.chunks_inserted))
        mini.add_row("documents stale", str(stats.documents_stale))
        mini.add_row("elapsed ms", str(stats.elapsed_ms))
        console.print(mini)

    # Write combined report for the whole scope run.
    if stats_total is not None:
        from rdos.rag.indexer import _write_index_report

        _write_index_report(stats_total, report_path)
        console.print(f"Report written to [cyan]{report_path}[/cyan]")
