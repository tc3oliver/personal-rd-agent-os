#!/usr/bin/env bash
# Demo: real corpus ingestion + retrieval. Requires local model stack.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> doctor models"
uv run rdos doctor models

echo
echo "==> index-corpus clawd-research --scope rag"
uv run rdos index-corpus --scope rag --embedding-provider local-bge-m3 clawd-research

echo
echo "==> index-corpus clawd-research --scope agent"
uv run rdos index-corpus --scope agent --embedding-provider local-bge-m3 clawd-research

echo
echo "==> index-corpus clawd-research --scope eval"
uv run rdos index-corpus --scope eval --embedding-provider local-bge-m3 clawd-research

echo
echo "==> search 'GraphRAG VectorRAG 層次化摘要'"
uv run rdos search --embedding-provider local-bge-m3 "GraphRAG VectorRAG 層次化摘要"

echo
echo "==> search 'AgentTrace 多智能體因果圖追蹤'"
uv run rdos search --embedding-provider local-bge-m3 "AgentTrace 多智能體因果圖追蹤"

echo
echo "Real corpus demo complete."
