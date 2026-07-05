#!/usr/bin/env bash
# Demo: v1.0 eval + benchmark.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[demo] Resetting deterministic demo index..."
rm -rf data/lancedb data/sqlite
mkdir -p data/lancedb data/sqlite data/traces data/reports data/generated data/samples
uv run rdos index --embedding-provider fake ./sample_data/notes
echo

echo "==> rdos eval all (8-metric gate + adversarial + opt-in)"
uv run rdos eval all

echo
echo "==> rdos eval adversarial (visibility-only summary)"
uv run rdos eval adversarial

echo
echo "==> rdos eval redaction"
uv run rdos eval redaction

echo
echo "==> rdos eval structured-output"
uv run rdos eval structured-output

echo
echo "==> rdos benchmark retrieval (fake provider, offline)"
uv run rdos benchmark retrieval --embedding-provider fake

echo
echo "==> rdos benchmark all (real provider — needs local model stack)"
echo "  (skipped: deterministic demo index uses fake embeddings)"

echo
echo "Eval demo complete."
