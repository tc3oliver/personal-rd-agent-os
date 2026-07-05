#!/usr/bin/env bash
# Demo: eval harness + benchmark.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "[demo] Resetting deterministic demo index..."
rm -rf data/lancedb data/sqlite
mkdir -p data/lancedb data/sqlite data/traces data/reports data/generated data/samples
uv run rdos index --embedding-provider fake ./sample_data/notes
echo

echo "==> rdos eval all (sample_data + fake provider)"
uv run rdos eval all

echo
echo "==> rdos benchmark retrieval (fake provider, offline)"
uv run rdos benchmark retrieval --embedding-provider fake --eval-set eval_sets/real_rag_qa.jsonl

echo
echo "==> rdos benchmark all (real provider — needs local model stack + real corpus)"
echo "  (skipped: deterministic demo index uses fake embeddings)"

echo
echo "Eval demo complete."
