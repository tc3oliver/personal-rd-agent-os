"""`rdos digest`, `rdos topic`, `rdos synthesize`."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rdos.apps.digest import run_digest
from rdos.apps.synthesize import run_synthesis
from rdos.apps.topic import run_topic_explorer
from rdos.config import get_config

app = typer.Typer(no_args_is_help=True, help="Daily digest / Topic explorer / Synthesis")
console = Console()


@app.command("digest")
def digest_cmd(
    since: str = typer.Option(..., "--since", help="YYYY-MM-DD"),
    collection: str = typer.Option("research-notes", "--collection"),
    embedding_provider: str = typer.Option(
        None, "--embedding-provider", help="fake | local-bge-m3"
    ),
) -> None:
    cfg = get_config()
    out, md = run_digest(
        cfg=cfg,
        since=since,
        source_collection=collection,
        embedding_provider=embedding_provider,
    )
    console.print(Panel.fit(f"Digest saved to {md}", title="Daily Digest"))
    table = Table(title="Digest summary")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("date", out.date)
    table.add_row("notes", str(len(out.notes)))
    table.add_row("clusters", str(len(out.clusters)))
    table.add_row("citations", str(len(out.citations)))
    table.add_row("privacy_level", out.privacy_level)
    console.print(table)


@app.command("topic")
def topic_cmd(
    topic: str = typer.Argument(..., help="Topic to explore"),
    collection: str = typer.Option("research-notes", "--collection"),
    since: str | None = typer.Option(None, "--since"),
    embedding_provider: str = typer.Option(
        None, "--embedding-provider", help="fake | local-bge-m3"
    ),
) -> None:
    cfg = get_config()
    out, md = run_topic_explorer(
        cfg=cfg,
        topic=topic,
        source_collection=collection,
        since=since,
        embedding_provider=embedding_provider,
    )
    console.print(Panel.fit(f"Topic explorer saved to {md}", title=f"Topic: {topic}"))
    table = Table(title="Topic summary")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("representative_notes", str(len(out.representative_notes)))
    table.add_row("related_topics", str(len(out.related_topics)))
    table.add_row("timeline_entries", str(len(out.timeline)))
    table.add_row("hot_keywords", ", ".join(out.hot_keywords[:8]))
    table.add_row("citations", str(len(out.citations)))
    console.print(table)


@app.command("synthesize")
def synthesize_cmd(
    question: str = typer.Argument(..., help="Synthesis question"),
    collection: str = typer.Option("research-notes", "--collection"),
    embedding_provider: str = typer.Option(
        None, "--embedding-provider", help="fake | local-bge-m3"
    ),
) -> None:
    cfg = get_config()
    out, md = run_synthesis(
        cfg=cfg,
        question=question,
        source_collection=collection,
        embedding_provider=embedding_provider,
    )
    console.print(Panel.fit(f"Synthesis saved to {md}", title="Synthesis"))
    table = Table(title="Synthesis summary")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("claims", str(len(out.claims)))
    table.add_row("citations", str(len(out.citations)))
    table.add_row("citation_coverage", f"{out.citation_coverage:.2%}")
    table.add_row("diverging_views", str(len(out.diverging_views)))
    table.add_row("privacy_level", out.privacy_level)
    console.print(table)
