#!/usr/bin/env bash
# Demo: eval harness + benchmark.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> rdos eval all (sample_data + fake provider)"
uv run rdos eval all

echo
echo "==> rdos benchmark retrieval (fake provider, offline)"
uv run rdos benchmark retrieval --embedding-provider fake --eval-set eval_sets/real_rag_qa.jsonl

echo
echo "==> rdos benchmark all (real provider — needs local model stack + real corpus)"
if uv run rdos doctor models >/dev/null 2>&1; then
  uv run rdos benchmark all --embedding-provider local-bge-m3 || echo "  (skipped: provider mismatch with current index)"
else
  echo "  (skipped: local model stack not reachable)"
fi

echo
echo "Eval demo complete."
