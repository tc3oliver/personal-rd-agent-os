#!/usr/bin/env bash
# Demo: foundation (offline-safe). No local model required.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "[demo] Resetting deterministic demo index..."
rm -rf data/lancedb data/sqlite
mkdir -p data/lancedb data/sqlite data/traces data/reports data/generated data/samples
uv run rdos index --embedding-provider fake ./sample_data/notes
echo

echo "==> pytest"
uv run pytest -q

echo
echo "==> ruff"
uv run ruff check .

echo
echo "==> rdos --help"
uv run rdos --help | head -16

echo
echo "==> rdos search 'RAG filtering'"
uv run rdos search --embedding-provider fake "RAG filtering"

echo
echo "==> rdos ask (stub mode, no local model needed)"
uv run rdos ask --llm-mode stub --embedding-provider fake "RAG filtering 是什麼？"

echo
echo "==> rdos eval all"
uv run rdos eval all

echo
echo "Foundation demo complete."
