#!/usr/bin/env bash
# Demo: v1.0 trust runtime (HITL approval + redaction + thread).
# Offline-safe — uses fake/stub providers where possible.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> rdos tool policy-check export_report --privacy private_raw"
uv run rdos tool policy-check export_report --privacy private_raw

echo
echo "==> rdos redaction eval"
uv run rdos redaction eval

echo
echo "==> rdos redaction scan 'contact alice@example.com or 0912345678'"
uv run rdos redaction scan "contact alice@example.com or 0912345678"

echo
echo "==> rdos approval list (may be empty)"
uv run rdos approval list || true

echo
echo "==> rdos thread new"
# Use Python to create thread and capture id cleanly (Rich panels wrap output)
TID=$(uv run python -c "
from rdos.threads.store import ThreadStore
s = ThreadStore('data/threads.db')
state = s.create(source_collection='sample_data', privacy_level='private_raw')
print(state.thread_id)
s.close()
" 2>/dev/null | tail -1)
if [ -z "$TID" ]; then
  echo "  (could not create thread; skipping thread-dependent demos)"
  echo "Trust runtime demo complete (partial)."
  exit 0
fi
echo "Created thread: $TID"
uv run rdos thread show "$TID" 2>&1 | head -5

echo
echo "==> rdos thread list"
uv run rdos thread list

echo
echo "==> rdos thread show $TID"
uv run rdos thread show "$TID" | head -30

echo
echo "==> rdos thread close $TID"
uv run rdos thread close "$TID"

echo
echo "Trust runtime demo complete."
