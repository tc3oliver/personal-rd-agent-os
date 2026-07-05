"""`rdos eval rag|citation|model-routing|privacy|no-answer|redaction|all`."""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from rdos.config import get_config
from rdos.eval.adversarial import (
    evaluate_citation_adversarial,
    evaluate_model_routing_adversarial,
    evaluate_privacy_adversarial,
)
from rdos.eval.citation_eval import evaluate_citation
from rdos.eval.model_routing_eval import evaluate_model_routing
from rdos.eval.no_answer_eval import evaluate_no_answer
from rdos.eval.privacy_eval import evaluate_privacy
from rdos.eval.rag_eval import evaluate_rag
from rdos.eval.redaction_eval import evaluate_redaction
from rdos.eval.report import (
    NO_ANSWER_GATE,
    REDACTION_GATE,
    RELEASE_GATE,
    write_report,
)
from rdos.eval.structured_output_eval import evaluate_structured_output

app = typer.Typer(no_args_is_help=True, help="Run eval harness")
console = Console()


def _gate_line(name: str, value: float, gate: dict[str, tuple[str, float]]) -> tuple[str, str]:
    if name not in gate:
        return "?", "?"
    op, threshold = gate[name]
    if op == "gte":
        ok = value >= threshold
        return ("PASS" if ok else "FAIL"), f"{op} {threshold:.2f}"
    if op == "lte":
        ok = value <= threshold
        return ("PASS" if ok else "FAIL"), f"{op} {threshold:.2f}"
    if op == "eq":
        ok = abs(value - threshold) < 1e-9
        return ("PASS" if ok else "FAIL"), f"{op} {threshold:.2f}"
    return "?", "?"


def _print_gate_table(title: str, metrics: dict[str, float], gate: dict[str, tuple[str, float]]) -> None:
    table = Table(title=title)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_column("Target", style="dim")
    table.add_column("Status")
    for name, value in metrics.items():
        status, _summary = _gate_line(name, value, gate)
        op_threshold = gate.get(name, ("?", 0.0))
        table.add_row(name, f"{value:.4f}", f"{op_threshold[0]} {op_threshold[1]:.2f}", status)
    console.print(table)


def _run_all() -> dict[str, Any]:
    """Run baseline + adversarial + opt-in gates. Return code-relevant payload."""
    cfg = get_config()

    # ----- Baseline gate -----
    rag = evaluate_rag(cfg)
    cit = evaluate_citation(cfg)
    mr = evaluate_model_routing(cfg)
    priv = evaluate_privacy(cfg)
    so = evaluate_structured_output()

    metrics = {
        "rag_recall_at_5": rag["value"],
        "citation_accuracy": cit["metrics"]["citation_accuracy"],
        "valid_chunk_reference_rate": cit["metrics"]["valid_chunk_reference_rate"],
        "structured_output_json_validity": so["value"],
        "model_routing_correct_rate": mr["value"],
        "privacy_policy_compliance": priv["metrics"]["privacy_policy_compliance"],
        "private_raw_leakage_rate": priv["metrics"]["private_raw_leakage_rate"],
        "company_sensitive_leakage_rate": priv["metrics"]["company_sensitive_leakage_rate"],
    }

    # ----- Adversarial (audit P1-1) — actually executed now -----
    cit_adv = evaluate_citation_adversarial(cfg)
    mr_adv = evaluate_model_routing_adversarial(cfg)
    priv_adv = evaluate_privacy_adversarial(cfg)

    # ----- Opt-in gates (audit P1-4) -----
    no_answer = evaluate_no_answer(cfg)
    redaction = evaluate_redaction()

    results = {
        "rag": rag,
        "citation": cit,
        "model_routing": mr,
        "privacy": priv,
        "structured_output": so,
        "citation_adversarial": cit_adv,
        "model_routing_adversarial": mr_adv,
        "privacy_adversarial": priv_adv,
        "no_answer": no_answer,
        "redaction": redaction,
    }

    overall, path = write_report(metrics, results)

    # ----- Print baseline gate -----
    _print_gate_table("Release Gate (foundation regression)", metrics, RELEASE_GATE)

    # ----- Print adversarial summary (audit P1-1 visibility) -----
    adv_table = Table(title="Adversarial eval (visibility only; not in release gate)")
    adv_table.add_column("Set", style="cyan")
    adv_table.add_column("Status", style="magenta")
    adv_table.add_column("Highlight", style="white")
    if not cit_adv.get("skipped"):
        adv_table.add_row(
            "citation_adversarial", "executed",
            f"accuracy={cit_adv['metrics'].get('citation_accuracy', 0):.4f}",
        )
    else:
        adv_table.add_row("citation_adversarial", "skipped", cit_adv.get("reason", ""))
    if not mr_adv.get("skipped"):
        adv_table.add_row(
            "model_routing_adversarial", "executed", f"correct={mr_adv.get('value', 0):.4f}"
        )
    else:
        adv_table.add_row("model_routing_adversarial", "skipped", mr_adv.get("reason", ""))
    if not priv_adv.get("skipped"):
        adv_table.add_row(
            "privacy_adversarial", "executed",
            f"compliance={priv_adv['metrics'].get('privacy_policy_compliance', 0):.4f}",
        )
    else:
        adv_table.add_row("privacy_adversarial", "skipped", priv_adv.get("reason", ""))
    console.print(adv_table)

    # ----- Print opt-in gates -----
    na_metrics = {
        "no_answer_accuracy": no_answer["no_answer_accuracy"],
        "false_no_answer_rate": no_answer["false_no_answer_rate"],
    }
    _print_gate_table("No-answer gate (opt-in; not in release gate)", na_metrics, NO_ANSWER_GATE)
    red_metrics = {
        "redaction_recall": redaction["redaction_recall"],
        "redaction_precision": redaction["redaction_precision"],
    }
    _print_gate_table("Redaction gate (opt-in; not in release gate)", red_metrics, REDACTION_GATE)

    console.print(f"[bold]Verdict: {'PASS' if overall else 'FAIL'}[/bold]")
    console.print(f"Report written to [cyan]{path}[/cyan]")
    return {"overall": overall, "metrics": metrics, "path": path}


@app.callback(invoke_without_command=True)
def eval_cmd(
    ctx: typer.Context,
) -> None:
    """Default: run all evals. Subcommands run a single eval."""
    if ctx.invoked_subcommand is not None:
        return
    payload = _run_all()
    if not payload["overall"]:
        raise typer.Exit(code=1)


@app.command("rag")
def rag_cmd() -> None:
    cfg = get_config()
    out = evaluate_rag(cfg)
    table = Table(title="RAG Recall@5")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row(out["metric"], f"{out['value']:.4f}")
    console.print(table)


@app.command("citation")
def citation_cmd() -> None:
    cfg = get_config()
    out = evaluate_citation(cfg)
    table = Table(title="Citation eval")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for k, v in out["metrics"].items():
        table.add_row(k, f"{v:.4f}")
    console.print(table)


@app.command("model-routing")
def model_routing_cmd() -> None:
    cfg = get_config()
    out = evaluate_model_routing(cfg)
    table = Table(title="Model routing eval")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row(out["metric"], f"{out['value']:.4f}")
    console.print(table)


@app.command("privacy")
def privacy_cmd() -> None:
    cfg = get_config()
    out = evaluate_privacy(cfg)
    table = Table(title="Privacy routing eval")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for k, v in out["metrics"].items():
        table.add_row(k, f"{v:.4f}")
    console.print(table)


@app.command("no-answer")
def no_answer_cmd() -> None:
    """Opt-in no-answer eval (audit P1-4)."""
    cfg = get_config()
    out = evaluate_no_answer(cfg)
    table = Table(title="No-answer eval")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("no_answer_accuracy", f"{out['no_answer_accuracy']:.4f}")
    table.add_row("false_no_answer_rate", f"{out['false_no_answer_rate']:.4f}")
    table.add_row("no_answer_samples", str(out["no_answer_samples"]))
    table.add_row("real_samples", str(out["real_samples"]))
    console.print(table)


@app.command("redaction")
def redaction_cmd() -> None:
    """Opt-in redaction eval (audit P1-4)."""
    out = evaluate_redaction()
    table = Table(title="Redaction eval")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("redaction_recall", f"{out['redaction_recall']:.4f}")
    table.add_row("redaction_precision", f"{out['redaction_precision']:.4f}")
    table.add_row("samples", str(out["samples"]))
    console.print(table)


@app.command("structured-output")
def structured_output_cmd() -> None:
    """Measure ResearchAnswer JSON round-trip (audit P1-3)."""
    out = evaluate_structured_output()
    table = Table(title="Structured output eval")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row(out["metric"], f"{out['value']:.4f}")
    table.add_row("samples", str(out["samples"]))
    table.add_row("valid", str(out["valid"]))
    console.print(table)


@app.command("adversarial")
def adversarial_cmd() -> None:
    """Run all adversarial evals (audit P1-1)."""
    cfg = get_config()
    cit = evaluate_citation_adversarial(cfg)
    mr = evaluate_model_routing_adversarial(cfg)
    priv = evaluate_privacy_adversarial(cfg)
    table = Table(title="Adversarial eval")
    table.add_column("Set", style="cyan")
    table.add_column("Status")
    table.add_column("Highlight", style="white")
    if not cit.get("skipped"):
        table.add_row(
            "citation_adversarial", "executed",
            f"accuracy={cit['metrics'].get('citation_accuracy', 0):.4f}",
        )
    else:
        table.add_row("citation_adversarial", "skipped", cit.get("reason", ""))
    if not mr.get("skipped"):
        table.add_row(
            "model_routing_adversarial", "executed", f"correct={mr.get('value', 0):.4f}"
        )
    else:
        table.add_row("model_routing_adversarial", "skipped", mr.get("reason", ""))
    if not priv.get("skipped"):
        table.add_row(
            "privacy_adversarial", "executed",
            f"compliance={priv['metrics'].get('privacy_policy_compliance', 0):.4f}",
        )
    else:
        table.add_row("privacy_adversarial", "skipped", priv.get("reason", ""))
    console.print(table)


@app.command("all")
def all_cmd() -> None:
    payload = _run_all()
    if not payload["overall"]:
        raise typer.Exit(code=1)
