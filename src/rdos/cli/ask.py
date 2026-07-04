"""`rdos ask "question"` — run the research_memory_graph end-to-end."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from rdos.config import get_config
from rdos.graph.research_memory_graph import build_research_memory_graph
from rdos.llm.runtime_mode import resolve_llm
from rdos.rag.embedding import build_embedding_provider
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.trace import TraceMetrics
from rdos.trace.trace_logger import Timer, new_run_id, now_iso
from rdos.trace.trace_store import JsonlTraceStore, build_record_from_state

app = typer.Typer(no_args_is_help=True, help="Ask the research_memory agent")
console = Console()


@app.callback(invoke_without_command=True)
def ask_cmd(
    question: str = typer.Argument(..., help="Question to ask the research_memory agent"),
    llm_mode: str = typer.Option(
        "auto",
        "--llm-mode",
        help="stub | local | auto (default: auto)",
    ),
    embedding_provider: str = typer.Option(
        None,
        "--embedding-provider",
        help="fake | local-bge-m3 (default: from config)",
    ),
    no_trace: bool = typer.Option(False, "--no-trace", help="Skip writing to JSONL trace"),
) -> None:
    """Run the full research_memory pipeline and print the answer."""
    cfg = get_config()
    provider_name = embedding_provider or cfg.models.embedding.provider
    dim = cfg.models.embedding.dim or cfg.rag.embedding.dim

    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=dim)
    embedding = build_embedding_provider(provider_name, dim=dim)
    vectors.ensure_provider_compatible(embedding)

    try:
        llm_decision = resolve_llm(cfg.models, llm_mode)
    except RuntimeError as exc:
        console.print(f"[red]LLM mode error:[/red] {exc}")
        raise typer.Exit(code=3) from exc
    if llm_decision.warning:
        console.print(f"[yellow]WARNING:[/yellow] {llm_decision.warning}")

    graph = build_research_memory_graph(
        config=cfg,
        sqlite_store=store,
        vector_store=vectors,
        embedding=embedding,
        llm=llm_decision.adapter,
    )
    timer = Timer()
    state = graph.run(question)
    answer = state.get("final_answer")

    # Attach runtime/llm/embedding metadata to state for trace consumption.
    state.setdefault("runtime_meta", {})
    state["runtime_meta"]["requested_llm_mode"] = llm_mode
    state["runtime_meta"]["actual_llm_adapter"] = type(llm_decision.adapter).__name__
    state["runtime_meta"]["fallback_used"] = llm_decision.fallback_used
    state["runtime_meta"]["fallback_reason"] = llm_decision.fallback_reason
    state["runtime_meta"]["embedding_provider"] = embedding.name
    state["runtime_meta"]["embedding_model"] = embedding.model
    state["runtime_meta"]["embedding_dim"] = int(embedding.dim)

    run_id = new_run_id()
    if not no_trace:
        trace_store = JsonlTraceStore("data/traces/runs.jsonl")
        record = build_record_from_state(
            state,
            run_id=run_id,
            timestamp=now_iso(),
            metrics=TraceMetrics(latency_ms=timer.elapsed_ms()),
        )
        # Annotate runtime metadata into the trace record.
        record.metrics.extra.update(state["runtime_meta"])
        trace_store.append(record)

    if answer is None:
        console.print("[red]No answer produced.[/red]")
        raise typer.Exit(code=1)

    console.print(
        Panel(answer.answer or "(empty answer)", title="Answer", border_style="cyan")
    )

    if answer.citations:
        from rich.table import Table

        table = Table(title="Citations", show_lines=False)
        table.add_column("#", style="dim")
        table.add_column("file", style="cyan")
        table.add_column("heading_path", style="magenta")
        table.add_column("chunk_id", style="dim")
        for i, c in enumerate(answer.citations, 1):
            table.add_row(
                str(i),
                c.file_path,
                " > ".join(c.heading_path) or "-",
                c.chunk_id[:12],
            )
        console.print(table)

    console.print(
        Panel.fit(
            f"Model:    {answer.selected_model_profile}\n"
            f"Privacy:  {answer.effective_privacy_level.value}\n"
            f"Confidence: {answer.confidence:.2f}\n"
            f"Run id:   {run_id[:12]}\n"
            f"LLM mode: {llm_mode} → {type(llm_decision.adapter).__name__}"
            + (" (fallback)" if llm_decision.fallback_used else ""),
            title="Routing",
        )
    )

    store.close()
