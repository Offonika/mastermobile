#!/usr/bin/env bash
set -euo pipefail

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for the ChatKit smoke test." >&2
  exit 2
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for the ChatKit smoke test." >&2
  exit 2
fi

BASE_URL=${CHATKIT_BASE_URL:-http://localhost:8000}
REQUEST_ID=${CHATKIT_SMOKE_REQUEST_ID:-chatkit-smoke-$(date +%s)}
THREAD_ID=${CHATKIT_SMOKE_THREAD_ID:-chatkit-smoke-thread}
QUERY=${CHATKIT_SMOKE_QUERY:-"Smoke test: search docs"}
MAX_ATTEMPTS=${CHATKIT_SMOKE_MAX_ATTEMPTS:-30}
RETRY_DELAY=${CHATKIT_SMOKE_RETRY_DELAY:-2}

trim_trailing_slash() {
  local value="$1"
  while [[ "$value" == */ ]]; do
    value=${value%/}
  done
  printf '%s' "$value"
}

API_ROOT="$(trim_trailing_slash "$BASE_URL")/api/v1/chatkit"
SESSION_URL="$API_ROOT/session"
WIDGET_ACTION_URL="$API_ROOT/widget-action"
HEALTH_URL="$(trim_trailing_slash "$BASE_URL")/health"

wait_for_service() {
  local url="$1"
  local attempt=1

  while (( attempt <= MAX_ATTEMPTS )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "[chatkit-smoke] Service is healthy at $url" >&2
      return 0
    fi

    echo "[chatkit-smoke] Waiting for service health ($attempt/$MAX_ATTEMPTS)" >&2
    sleep "$RETRY_DELAY"
    ((attempt++))
  done

  echo "[chatkit-smoke] Service did not become healthy at $url" >&2
  return 1
}

wait_for_service "$HEALTH_URL"

echo "[chatkit-smoke] Requesting session from $SESSION_URL" >&2
session_response=$(curl -fsS -X POST \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: ${REQUEST_ID}-session" \
  "$SESSION_URL")

client_secret=$(printf '%s' "$session_response" | jq -er '.client_secret | select(type == "string" and length > 0)')

echo "[chatkit-smoke] Received client secret (${#client_secret} bytes)" >&2

widget_payload=$(jq -n \
  --arg thread "$THREAD_ID" \
  --arg query "$QUERY" \
  '{type:"tool", name:"search-docs", payload:{thread_id:$thread, query:$query}}')

echo "[chatkit-smoke] Sending widget action to $WIDGET_ACTION_URL" >&2
widget_response=$(curl -fsS -X POST \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: ${REQUEST_ID}-widget" \
  -H "X-Chatkit-Thread-Id: $THREAD_ID" \
  -d "$widget_payload" \
  "$WIDGET_ACTION_URL")

printf '%s' "$widget_response" | jq -e 'select(.ok == true and (.awaiting_query == true))' >/dev/null

echo "[chatkit-smoke] Widget action acknowledged successfully." >&2
