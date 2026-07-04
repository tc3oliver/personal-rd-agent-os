#!/usr/bin/env bash
# Demo: foundation (offline-safe). No local model required.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> pytest"
uv run pytest -q

echo
echo "==> ruff"
uv run ruff check .

echo
echo "==> rdos --help"
uv run rdos --help | head -16

echo
echo "==> rdos index ./sample_data/notes"
uv run rdos index ./sample_data/notes

echo
echo "==> rdos search 'RAG filtering'"
uv run rdos search "RAG filtering"

echo
echo "==> rdos ask (stub mode, no local model needed)"
uv run rdos ask --llm-mode stub "RAG filtering 是什麼？"

echo
echo "==> rdos eval all"
uv run rdos eval all

echo
echo "Foundation demo complete."
