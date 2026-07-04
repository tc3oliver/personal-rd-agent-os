"""`rdos doctor` — system health checks."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, help="System health checks")


@app.command("models")
def models_cmd() -> None:
    """Check local model stack (chat + embedding endpoints)."""
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "check_local_model_stack.py"
    if not script.exists():
        typer.echo(f"script not found: {script}", err=True)
        raise typer.Exit(code=2)
    raise typer.Exit(code=subprocess.call([sys.executable, str(script)]))
