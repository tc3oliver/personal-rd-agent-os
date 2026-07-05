#!/usr/bin/env bash
# Demo: v1.0 research thread (multi-turn).
# Requires local model stack — falls back gracefully if unavailable.
set -euo pipefail
cd "$(dirname "$0")/.."

PROVIDER="${RDOS_DEMO_PROVIDER:-fake}"
LLM_MODE="${RDOS_DEMO_LLM_MODE:-stub}"

echo "==> Provider: $PROVIDER  /  LLM mode: $LLM_MODE"
echo

echo "==> rdos thread new"
TID=$(uv run python -c "
from rdos.threads.store import ThreadStore
s = ThreadStore('data/threads.db')
state = s.create(source_collection='sample_data', privacy_level='private_raw')
print(state.thread_id)
s.close()
" 2>/dev/null | tail -1)
if [ -z "$TID" ]; then
  echo "  (could not create thread; aborting)"
  exit 1
fi
echo "Thread: $TID"

echo
echo "==> Turn 1: rdos thread ask $TID 'What is RAG filtering?'"
uv run rdos thread ask "$TID" "What is RAG filtering?" \
  --embedding-provider "$PROVIDER" --llm-mode "$LLM_MODE"

echo
echo "==> Turn 2: rdos thread ask $TID 'How does it compare to semantic search?'"
uv run rdos thread ask "$TID" "How does it compare to semantic search?" \
  --embedding-provider "$PROVIDER" --llm-mode "$LLM_MODE"

echo
echo "==> Turn 3: rdos thread ask $TID 'can you give an example?'"
uv run rdos thread ask "$TID" "can you give an example?" \
  --embedding-provider "$PROVIDER" --llm-mode "$LLM_MODE"

echo
echo "==> rdos thread show $TID (full conversation)"
uv run rdos thread show "$TID"

echo
echo "==> rdos thread close $TID"
uv run rdos thread close "$TID"

echo
echo "Research thread demo complete."
