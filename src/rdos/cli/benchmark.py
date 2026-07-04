"""`rdos benchmark retrieval` and `rdos benchmark all`."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rdos.config import get_config
from rdos.eval.retrieval_benchmark import benchmark_retrieval

app = typer.Typer(no_args_is_help=True, help="Run retrieval / pipeline benchmarks")
console = Console()


@app.callback(invoke_without_command=True)
def benchmark_cmd(
    ctx: typer.Context,
    embedding_provider: str = typer.Option(
        None, "--embedding-provider", help="fake | local-bge-m3"
    ),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    _run_retrieval(embedding_provider)


@app.command("retrieval")
def retrieval_cmd(
    embedding_provider: str = typer.Option(
        None, "--embedding-provider", help="fake | local-bge-m3"
    ),
    eval_set: str = typer.Option(
        "eval_sets/real_rag_qa.jsonl", "--eval-set", help="Eval set JSONL path"
    ),
) -> None:
    _run_retrieval(embedding_provider, eval_set=eval_set)


@app.command("all")
def all_cmd(
    embedding_provider: str = typer.Option(
        None, "--embedding-provider", help="fake | local-bge-m3"
    ),
) -> None:
    out = _run_retrieval(embedding_provider)
    # Also dump a small benchmark_report.md
    report_path = Path("data/reports/benchmark_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# RDOS Benchmark Report", "", f"_Embedding: {out['embedding_provider']}_", ""]
    lines.append("## Retrieval benchmark")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    for k, v in out.items():
        if k in ("results", "metric", "embedding_provider"):
            continue
        if isinstance(v, float):
            lines.append(f"| {k} | {v:.4f} |")
        else:
            lines.append(f"| {k} | {v} |")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"Report written to [cyan]{report_path}[/cyan]")


def _run_retrieval(embedding_provider: str | None, *, eval_set: str = "eval_sets/real_rag_qa.jsonl") -> dict:
    cfg = get_config()
    out = benchmark_retrieval(cfg, embedding_provider=embedding_provider, eval_set=eval_set)
    table = Table(title="Retrieval Benchmark")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    for k, v in out.items():
        if k in ("results",):
            continue
        if isinstance(v, float):
            table.add_row(k, f"{v:.4f}")
        else:
            table.add_row(k, str(v))
    console.print(table)
    return out
