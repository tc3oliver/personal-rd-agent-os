#!/usr/bin/env bash
# Demo: v1.0 foundation pipeline (offline-safe, no local model required).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> pytest"
uv run pytest -q

echo
echo "==> ruff"
uv run ruff check .

echo
echo "==> rdos --help (14 commands expected)"
uv run rdos --help | head -25

echo
echo "==> rdos index ./sample_data/notes (fake provider, deterministic)"
uv run rdos index ./sample_data/notes --embedding-provider fake

echo
echo "==> rdos search 'RAG filtering'"
uv run rdos search "RAG filtering" --embedding-provider fake

echo
echo "==> rdos ask (stub LLM, no local model needed)"
uv run rdos ask "RAG filtering 是什麼？" --llm-mode stub --embedding-provider fake

echo
echo "==> rdos trace list"
uv run rdos trace list

echo
echo "==> rdos eval all (8-metric release gate)"
uv run rdos eval all

echo
echo "Foundation demo complete."
