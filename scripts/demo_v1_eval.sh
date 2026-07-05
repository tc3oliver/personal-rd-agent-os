#!/usr/bin/env bash
# Demo: v1.0 eval + benchmark.
set -euo pipefail
cd "$(dirname "$0")/.."

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
if uv run rdos doctor models >/dev/null 2>&1; then
  uv run rdos benchmark all --embedding-provider local-bge-m3 \
    || echo "  (skipped: provider mismatch with current index — reindex first)"
else
  echo "  (skipped: local model stack not reachable)"
fi

echo
echo "Eval demo complete."
