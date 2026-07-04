#!/usr/bin/env bash
# Demo: trace store.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> rdos ask (writes trace)"
uv run rdos ask --llm-mode stub "RAG filtering 是什麼？"

echo
echo "==> rdos trace list"
uv run rdos trace list

echo
RUN_ID=$(uv run rdos trace list | awk 'FNR==4 {print $1}' | head -1)
if [ -n "$RUN_ID" ]; then
  echo "==> rdos trace show $RUN_ID (first 1000 chars)"
  uv run rdos trace show "$RUN_ID" | head -c 1000
  echo
fi
echo
echo "Trace demo complete."
