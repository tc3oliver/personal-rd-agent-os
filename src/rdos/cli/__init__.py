"""RDOS CLI entry point."""

from __future__ import annotations

import typer

from rdos.cli.ask import app as ask_app
from rdos.cli.benchmark import app as benchmark_app
from rdos.cli.corpus import app as corpus_app
from rdos.cli.doctor import app as doctor_app
from rdos.cli.eval import app as eval_app
from rdos.cli.index import app as index_app
from rdos.cli.research_apps import app as research_apps_app
from rdos.cli.search import app as search_app
from rdos.cli.tool import app as tool_app
from rdos.cli.trace import app as trace_app

app = typer.Typer(
    name="rdos",
    help="Personal R&D Agent OS — model-agnostic, privacy-aware, evaluation-driven.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(index_app, name="index")
app.add_typer(corpus_app, name="index-corpus")
app.add_typer(search_app, name="search")
app.add_typer(ask_app, name="ask")
app.add_typer(trace_app, name="trace")
app.add_typer(eval_app, name="eval")
app.add_typer(doctor_app, name="doctor")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(tool_app, name="tool")
app.add_typer(research_apps_app, name="research")


@app.command()
def version() -> None:
    """Print RDOS version."""
    from rdos import __version__

    typer.echo(__version__)


@app.command()
def hello() -> None:
    """Placeholder command to verify CLI wiring."""
    typer.echo("rdos skeleton ready")


if __name__ == "__main__":
    app()
