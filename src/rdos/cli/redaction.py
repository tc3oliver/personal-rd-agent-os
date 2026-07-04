"""`rdos eval redaction` and `rdos redaction scan <text>`."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rdos.eval.redaction_eval import evaluate_redaction
from rdos.llm.redaction import load_redaction_config, redact

app = typer.Typer(no_args_is_help=True, help="Redaction scan + eval")
console = Console()


@app.command("scan")
def scan_cmd(
    text: str = typer.Argument(..., help="Text to scan"),
    strategy: str = typer.Option(None, "--strategy", help="placeholder|mask|hash"),
) -> None:
    cfg = load_redaction_config()
    if strategy:
        cfg["replacement_strategy"] = strategy
    out, recs = redact(text, cfg)
    table = Table(title="Recognitions")
    table.add_column("type", style="cyan")
    table.add_column("text", style="white")
    table.add_column("replacement", style="magenta")
    for r in recs:
        table.add_row(r.type, r.text[:40], r.replacement)
    console.print(table)
    console.print(f"\n[bold]Redacted:[/bold] {out}")


@app.command("eval")
def eval_cmd(
    eval_set: str | None = typer.Option(None, "--eval-set", help="Optional JSONL"),
) -> None:
    out = evaluate_redaction(eval_set=eval_set)
    table = Table(title="Redaction eval")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("samples", str(out["samples"]))
    table.add_row("redaction_recall", f"{out['redaction_recall']:.4f}")
    table.add_row("redaction_precision", f"{out['redaction_precision']:.4f}")
    table.add_row("expected_total", str(out["expected_total"]))
    table.add_row("caught", str(out["caught"]))
    table.add_row("false_positives", str(out["false_positives"]))
    console.print(table)


# silence unused
_ = Path
