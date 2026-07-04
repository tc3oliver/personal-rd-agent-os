"""RDOS CLI entry point."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="rdos",
    help="Personal R&D Agent OS — model-agnostic, privacy-aware, evaluation-driven.",
    no_args_is_help=True,
    add_completion=False,
)


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
#   index   (Batch 3)
#   search  (Batch 4)
#   ask     (Batch 7)
#   trace   (Batch 8)
#   eval    (Batch 9)


if __name__ == "__main__":
    app()
