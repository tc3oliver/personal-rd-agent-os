"""`rdos ask "question"` — run the research_memory_graph end-to-end."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from rdos.config import get_config
from rdos.graph.research_memory_graph import build_research_memory_graph
from rdos.llm.local_llama_cpp import LocalLlamaCppAdapter
from rdos.llm.provider import LLMAdapter, StubLLMAdapter
from rdos.rag.embedding import build_embedding_provider
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.trace.trace_logger import Timer, record_run
from rdos.trace.trace_store import JsonlTraceStore

app = typer.Typer(no_args_is_help=True, help="Ask the research_memory agent")
console = Console()


def _resolve_llm(cfg, *, force_stub: bool) -> LLMAdapter:
    """Use the local llama.cpp adapter if reachable; otherwise stub for offline dev."""
    if force_stub:
        return StubLLMAdapter(model="stub", provider="stub")
    try:
        adapter = LocalLlamaCppAdapter.from_config(cfg.models, "local_fast")
        if adapter.health():
            return adapter
        return StubLLMAdapter(model="stub", provider="stub")
    except Exception:  # noqa: BLE001
        return StubLLMAdapter(model="stub", provider="stub")


@app.callback(invoke_without_command=True)
def ask_cmd(
    question: str = typer.Argument(..., help="Question to ask the research_memory agent"),
    stub: bool = typer.Option(False, "--stub", help="Force stub LLM even if local server is up"),
    no_trace: bool = typer.Option(False, "--no-trace", help="Skip writing to JSONL trace"),
) -> None:
    """Run the full research_memory pipeline and print the answer."""
    cfg = get_config()
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(
        cfg.rag.storage.lancedb_path,
        dim=cfg.models.embedding.dim or cfg.rag.embedding.dim,
    )
    embedding = build_embedding_provider(
        provider=cfg.models.embedding.provider,
        dim=cfg.models.embedding.dim or cfg.rag.embedding.dim,
    )
    llm = _resolve_llm(cfg, force_stub=stub)

    graph = build_research_memory_graph(
        config=cfg,
        sqlite_store=store,
        vector_store=vectors,
        embedding=embedding,
        llm=llm,
    )
    timer = Timer()
    state = graph.run(question)
    answer = state.get("final_answer")

    if not no_trace:
        trace_store = JsonlTraceStore("data/traces/runs.jsonl")
        run_id = record_run(trace_store, state, timer=timer)
    else:
        run_id = "<trace-skipped>"

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
            f"Run id:   {run_id[:12]}",
            title="Routing",
        )
    )

    store.close()
