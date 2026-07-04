#!/usr/bin/env bash
# Compatibility check for the local llama.cpp server.
#
# Expects LOCAL_LLM_BASE_URL / LOCAL_LLM_MODEL / LOCAL_LLM_API_KEY to be set
# (the .env.example defaults work). Exits non-zero on any hard failure.

set -euo pipefail

BASE_URL="${LOCAL_LLM_BASE_URL:-http://10.10.10.12:8080}"
MODEL="${LOCAL_LLM_MODEL:-qwythos-9b-q4}"
API_KEY="${LOCAL_LLM_API_KEY:-local-dev-key}"

echo "==> Health check: $BASE_URL"
if ! curl -sf "$BASE_URL/health" >/dev/null; then
  echo "  [FAIL] health check did not return 200 — server may be down"
  exit 1
fi
echo "  OK"

echo "==> Models endpoint"
curl -sf "$BASE_URL/v1/models" -H "Authorization: Bearer $API_KEY" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('  ', d['data'][0]['id'])"

echo "==> Basic chat completion"
RESP=$(curl -sf "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d "{\"model\":\"$MODEL\",\"max_tokens\":1000,\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word: pong\"}]}")
echo "  $RESP" | python3 -c "import json,sys; r=json.loads(sys.stdin.read().strip().lstrip('  ')); print('  assistant:', r['choices'][0]['message']['content'][:80])"

echo "==> Streaming chat completion (first 2 chunks)"
curl -N -sf "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d "{\"model\":\"$MODEL\",\"stream\":true,\"max_tokens\":1000,\"messages\":[{\"role\":\"user\",\"content\":\"count to 5\"}]}" \
  | head -n 4

echo "==> JSON-mode chat completion"
curl -sf "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d "{\"model\":\"$MODEL\",\"max_tokens\":1000,\"response_format\":{\"type\":\"json_object\"},\"messages\":[{\"role\":\"user\",\"content\":\"Return JSON {\\\"ok\\\": true}\"}]}" \
  | python3 -c "import json,sys; r=json.load(sys.stdin); print('  parsed:', r['choices'][0]['message']['content'][:80])"

echo
echo "All checks passed."
