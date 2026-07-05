"""`rdos thread new|ask|list|show|close` — multi-turn research CLI."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rdos.config import get_config
from rdos.graph.langgraph_runtime import build_langgraph_runtime
from rdos.llm.runtime_mode import resolve_llm
from rdos.rag.embedding import build_embedding_provider
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.trace import TraceMetrics
from rdos.threads.rewriter import maybe_compress, rewrite_followup
from rdos.threads.store import ThreadStore, add_turn
from rdos.trace.trace_logger import Timer, new_run_id, now_iso
from rdos.trace.trace_store import JsonlTraceStore, build_record_from_state

app = typer.Typer(no_args_is_help=True, help="Multi-turn research thread")
console = Console()


@app.command("new")
def new_cmd(
    collection: str = typer.Option("clawd-research", "--collection"),
    privacy: str = typer.Option("private_raw", "--privacy"),
) -> None:
    store = ThreadStore("data/threads.db")
    state = store.create(source_collection=collection, privacy_level=privacy)
    console.print(
        Panel.fit(
            f"thread_id: {state.thread_id}\n"
            f"created_at: {state.created_at}\n"
            f"collection: {state.source_collection}\n"
            f"privacy: {state.privacy_level}",
            title="New Thread",
        )
    )
    store.close()


@app.command("ask")
def ask_cmd(
    thread_id: str = typer.Argument(..., help="Thread id (or unique prefix)"),
    question: str = typer.Argument(..., help="Follow-up question"),
    llm_mode: str = typer.Option("auto", "--llm-mode"),
    embedding_provider: str = typer.Option(None, "--embedding-provider"),
) -> None:
    cfg = get_config()
    store = ThreadStore("data/threads.db")
    state = store.get(thread_id)
    if state is None:
        for s in store.list_recent(limit=10_000):
            if s.thread_id.startswith(thread_id):
                state = s
                break
    if state is None:
        console.print(f"[red]No thread with id matching:[/red] {thread_id}")
        raise typer.Exit(code=2)
    if state.closed_at:
        console.print(f"[red]Thread closed at[/red] {state.closed_at}")
        raise typer.Exit(code=3)

    # Rewrite followup
    rewritten = rewrite_followup(state, question)
    if rewritten != question:
        console.print(f"[dim]rewrite:[/dim] {question} → {rewritten}")

    # P1-1 (Batch 23 audit fix): compose threaded retrieval query that
    # actually carries forward prior context. context_for_new_turn returns
    # prior turns / cited chunk_ids / compressed summary. We prepend a
    # prior-context block so the keyword channel of HybridRetriever can
    # pick up topics from earlier turns.
    from rdos.threads.rewriter import context_for_new_turn

    ctx_payload = context_for_new_turn(state, max_turns=3)
    ctx_topics = []
    for t in ctx_payload.get("prior_turns", []):
        for tok in __import__("re").findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", t.get("question", "")):
            if tok.lower() not in {"the", "and", "for", "with", "what", "why", "how"}:
                ctx_topics.append(tok)
    ctx_cited = ctx_payload.get("cited_chunk_ids", [])[:5]
    ctx_block_parts: list[str] = []
    if ctx_topics:
        unique_topics: list[str] = []
        seen: set[str] = set()
        for t in ctx_topics:
            if t not in seen:
                unique_topics.append(t)
                seen.add(t)
        ctx_block_parts.append("prior topics: " + ", ".join(unique_topics[:6]))
    if ctx_cited:
        ctx_block_parts.append("prior cited: " + " ".join(ctx_cited))
    if ctx_block_parts:
        composed_query = rewritten + " | " + " ; ".join(ctx_block_parts)
    else:
        composed_query = rewritten
    if composed_query != rewritten:
        console.print(f"[dim]carry-forward:[/dim] {len(ctx_topics)} topic tokens, {len(ctx_cited)} cited ids")

    provider_name = embedding_provider or cfg.models.embedding.provider
    dim = cfg.models.embedding.dim or cfg.rag.embedding.dim
    sqlite_store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=dim)
    embedding = build_embedding_provider(provider_name, dim=dim)
    vectors.ensure_provider_compatible(embedding)
    llm_decision = resolve_llm(cfg.models, llm_mode)
    if llm_decision.warning:
        console.print(f"[yellow]WARNING:[/yellow] {llm_decision.warning}")

    runtime = build_langgraph_runtime(
        config=cfg,
        sqlite_store=sqlite_store,
        vector_store=vectors,
        embedding=embedding,
        llm=llm_decision.adapter,
    )
    timer = Timer()
    graph_state, langgraph_thread_id = runtime.invoke(composed_query)
    answer_obj = graph_state.get("final_answer")
    answer_text = answer_obj.answer if answer_obj else ""
    citations = graph_state.get("citations") or []
    cited_ids = [c.chunk_id for c in citations]

    run_id = new_run_id()
    add_turn(
        store,
        state,
        run_id=run_id,
        question=question,  # original, not rewritten
        answer=answer_text,
        citation_chunk_ids=cited_ids,
    )
    if maybe_compress(state, max_turns=5):
        store.update(state)
        console.print("[dim](memory compression applied)[/dim]")

    # Trace
    graph_state.setdefault("runtime_meta", {})
    graph_state["runtime_meta"]["graph_runtime"] = "langgraph"
    graph_state["runtime_meta"]["thread_id"] = state.thread_id
    graph_state["runtime_meta"]["turn_index"] = len(state.turns) - 1
    graph_state["runtime_meta"]["original_followup_query"] = question
    graph_state["runtime_meta"]["rewritten_query"] = rewritten
    graph_state["runtime_meta"]["composed_retrieval_query"] = composed_query
    graph_state["runtime_meta"]["context_for_new_turn_used"] = {
        "prior_topic_tokens": len(ctx_topics),
        "prior_cited_carried": len(ctx_cited),
    }
    graph_state["runtime_meta"]["original_query"] = question
    trace_store = JsonlTraceStore("data/traces/runs.jsonl")
    record = build_record_from_state(
        graph_state,
        run_id=run_id,
        timestamp=now_iso(),
        metrics=TraceMetrics(latency_ms=timer.elapsed_ms()),
    )
    record.metrics.extra.update(graph_state["runtime_meta"])
    trace_store.append(record)

    console.print(Panel(answer_text or "(no answer)", title=f"Turn {len(state.turns)}", border_style="cyan"))
    if citations:
        ct = Table(title="Citations")
        ct.add_column("#", style="dim")
        ct.add_column("file", style="cyan")
        ct.add_column("chunk_id", style="dim")
        for i, c in enumerate(citations, 1):
            ct.add_row(str(i), c.file_path, c.chunk_id[:12])
        console.print(ct)
    console.print(
        Panel.fit(
            f"thread:   {state.thread_id[:12]}\n"
            f"turn:     {len(state.turns)}\n"
            f"cited:    {len(cited_ids)} (carry-forward total: {len(state.cited_chunks)})\n"
            f"run_id:   {run_id[:12]}",
            title="Thread",
        )
    )
    sqlite_store.close()
    store.close()


@app.command("list")
def list_cmd(
    limit: int = typer.Option(20, "--limit", "-n"),
) -> None:
    store = ThreadStore("data/threads.db")
    items = store.list_recent(limit=limit)
    if not items:
        console.print("[yellow]No threads yet.[/yellow]")
        return
    table = Table(title="Threads")
    table.add_column("thread_id", style="dim")
    table.add_column("created_at", style="white")
    table.add_column("turns", justify="right")
    table.add_column("cited", justify="right")
    table.add_column("closed", style="magenta")
    for s in items:
        table.add_row(
            s.thread_id[:12],
            s.created_at,
            str(len(s.turns)),
            str(len(s.cited_chunks)),
            "yes" if s.closed_at else "-",
        )
    console.print(table)
    store.close()


@app.command("show")
def show_cmd(thread_id: str = typer.Argument(...)) -> None:
    store = ThreadStore("data/threads.db")
    state = store.get(thread_id)
    if state is None:
        for s in store.list_recent(limit=10_000):
            if s.thread_id.startswith(thread_id):
                state = s
                break
    if state is None:
        console.print(f"[red]No thread matching:[/red] {thread_id}")
        raise typer.Exit(code=1)
    console.print_json(json.dumps(state.model_dump(), ensure_ascii=False))
    store.close()


@app.command("close")
def close_cmd(thread_id: str = typer.Argument(...)) -> None:
    store = ThreadStore("data/threads.db")
    state = None
    state = store.get(thread_id)
    if state is None:
        for s in store.list_recent(limit=10_000):
            if s.thread_id.startswith(thread_id):
                state = s
                break
    if state is None:
        console.print(f"[red]No thread matching:[/red] {thread_id}")
        raise typer.Exit(code=1)
    closed = store.close_thread(state.thread_id)
    console.print(
        Panel.fit(
            f"thread_id: {closed.thread_id}\n"
            f"closed_at: {closed.closed_at}\n"
            f"turns:     {len(closed.turns)}",
            title="Closed",
        )
    )
    store.close()


def _silence(_: Any) -> None:
    return None
