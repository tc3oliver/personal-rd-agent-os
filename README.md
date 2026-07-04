# Personal R&D Agent OS (RDOS)

> Model-agnostic · Privacy-aware · Evaluation-driven personal R&D agent system

`rdos` is a local-first research memory & synthesis agent that turns personal Markdown notes into a queryable, citable, traceable knowledge base — with explicit privacy-aware model routing.

## Core loop

```
Markdown notes
  → index
  → retrieve
  → cite
  → calculate effective privacy
  → route model
  → generate answer
  → validate structured output
  → validate citations
  → save trace
  → run eval
  → show metrics
```

## Quick start

```bash
# Install (uv)
uv sync --extra dev

# Verify skeleton
uv run rdos --help
uv run pytest
uv run ruff check .

# Index sample notes
uv run rdos index ./sample_data/notes

# Ask a question
uv run rdos ask "我之前是不是看過一篇講 RAG filtering 的文章？"

# Inspect trace
uv run rdos trace list
uv run rdos trace show <run_id>

# Run eval
uv run rdos eval all
```

## Layout

```
configs/        YAML configs (models, privacy, rag, tool policy)
docs/           Architecture spec, batch plans, local model stack
src/rdos/       Source code
  cli/          Typer CLI commands
  schemas/      Pydantic data contracts
  rag/          Markdown parser, chunker, indexer, retriever, citation
  llm/          Provider interface, local llama.cpp adapter, structured output
  graph/        LangGraph state machines
  trace/        JSONL trace store
  eval/         Eval harness
  tools/        Tool permission layer
eval_sets/      Eval fixtures
sample_data/    Synthetic markdown notes
data/           Runtime data (lancedb, sqlite, traces, reports)
tests/          Unit tests
scripts/        Operational scripts
```

## Documentation

- [Architecture Spec](docs/architecture.md)
- [Batch Plan](docs/batches/README.md)
- [Local Model Stack](docs/local_model_stack.md)

## Status

See [docs/batches/README.md](docs/batches/README.md) for batch-by-batch progress.

## License

MIT
