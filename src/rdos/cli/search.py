"""`rdos search "query"` — hybrid retriever + citation preview."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from rdos.config import get_config
from rdos.rag.citation_builder import CitationBuilder
from rdos.rag.embedding import build_embedding_provider
from rdos.rag.retriever import HybridRetriever
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.privacy import PrivacyLevel

app = typer.Typer(no_args_is_help=True, help="Hybrid search over indexed notes")
console = Console()


@app.callback(invoke_without_command=True)
def search_cmd(
    query: str = typer.Argument(..., help="Search query"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Top K results"),
    privacy: str | None = typer.Option(
        None,
        "--privacy",
        help="Comma-separated privacy filter (e.g. public,private_summary)",
    ),
) -> None:
    """Run hybrid search over the indexed chunks."""
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

    from rdos.rag.hybrid_search import RetrievalFilters

    filters = RetrievalFilters()
    if privacy:
        filters.privacy_levels = [PrivacyLevel(p.strip()) for p in privacy.split(",") if p.strip()]

    retriever = HybridRetriever(
        sqlite_store=store,
        vector_store=vectors,
        embedding=embedding,
        config=cfg,
    )
    result = retriever.search(query, top_k=top_k, filters=filters)

    if not result.chunks:
        console.print("[yellow]No results.[/yellow]")
        raise typer.Exit(code=0)

    builder = CitationBuilder(max_citations=top_k)
    citations = builder.build(query, result)

    table = Table(title=f"Top results for: {query}")
    table.add_column("#", style="dim")
    table.add_column("Title", style="cyan")
    table.add_column("Heading path", style="magenta")
    table.add_column("Score", justify="right")
    table.add_column("Privacy", style="yellow")
    table.add_column("chunk_id", style="dim")

    for i, c in enumerate(citations, 1):
        table.add_row(
            str(i),
            c.title,
            " > ".join(c.heading_path) or "-",
            f"{c.score or 0:.4f}",
            "",  # privacy filled from chunk
            c.chunk_id[:12],
        )
    console.print(table)

    store.close()
