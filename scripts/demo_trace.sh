#!/usr/bin/env bash
# Demo: trace store.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "[demo] Resetting deterministic demo index..."
rm -rf data/lancedb data/sqlite
mkdir -p data/lancedb data/sqlite data/traces data/reports data/generated data/samples
uv run rdos index --embedding-provider fake ./sample_data/notes
echo

echo "==> rdos ask (writes trace)"
uv run rdos ask --llm-mode stub --embedding-provider fake "RAG filtering 是什麼？"

echo
echo "==> rdos trace list"
uv run rdos trace list

echo
RUN_ID=$(uv run python -c "
import json
from pathlib import Path

path = Path('data/traces/runs.jsonl')
if path.exists():
    lines = [line for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if lines:
        print(json.loads(lines[-1]).get('run_id', ''))
" 2>/dev/null | tail -1)
if [ -n "$RUN_ID" ]; then
  echo "==> rdos trace show $RUN_ID (first 1000 chars)"
  uv run rdos trace show "$RUN_ID" | head -c 1000
  echo
else
  echo "  (skipped: no trace run_id found)"
fi
echo
echo "Trace demo complete."
