"""RDOS CLI entry point."""

from __future__ import annotations

import typer

from rdos.cli.ask import app as ask_app
from rdos.cli.index import app as index_app
from rdos.cli.search import app as search_app

app = typer.Typer(
    name="rdos",
    help="Personal R&D Agent OS — model-agnostic, privacy-aware, evaluation-driven.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(index_app, name="index")
app.add_typer(search_app, name="search")
app.add_typer(ask_app, name="ask")


@app.command()
def version() -> None:
    """Print RDOS version."""
    from rdos import __version__

    typer.echo(__version__)


@app.command()
def hello() -> None:
    """Placeholder command to verify CLI wiring."""
    typer.echo("rdos skeleton ready")


# Sub-apps will be registered by later batches:
#   search  (Batch 4)
#   ask     (Batch 7)
#   trace   (Batch 8)
#   eval    (Batch 9)


if __name__ == "__main__":
    app()
