#!/usr/bin/env bash
# shellcheck disable=SC2155
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV_FILE="${PROJECT_ROOT}/.env"
MESSAGE="ping"

usage() {
    cat <<USAGE
Usage: ${0##*/} [--env-file PATH] [message]

Trigger the configured OpenAI Agent Builder workflow with a simple payload.

Options:
  --env-file PATH   Path to the .env file to read OPENAI_* values from (default: ${ENV_FILE}).
  -h, --help        Show this help message and exit.

If OPENAI_* variables are already exported in the environment they take precedence
over values loaded from the .env file.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file)
            if [[ $# -lt 2 ]]; then
                echo "Missing value for --env-file" >&2
                exit 1
            fi
            ENV_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --*)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
        *)
            MESSAGE="$1"
            shift
            ;;
    esac
done

load_env_value() {
    local key="$1"
    local file="$2"

    [[ -f "$file" ]] || return 1

    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        case "$line" in
            ""|\#*)
                continue
                ;;
            "${key}="*)
                echo "${line#${key}=}" | tr -d '\r'
                return 0
                ;;
        esac
    done < "$file"
    return 1
}

maybe_set_from_file() {
    local var_name="$1"
    local file="$2"

    if [[ -n "${!var_name:-}" ]]; then
        return
    fi

    local value
    if value="$(load_env_value "$var_name" "$file")"; then
        export "$var_name"="$value"
    fi
}

maybe_set_from_file OPENAI_API_KEY "$ENV_FILE"
maybe_set_from_file OPENAI_BASE_URL "$ENV_FILE"
maybe_set_from_file OPENAI_PROJECT "$ENV_FILE"
maybe_set_from_file OPENAI_ORG "$ENV_FILE"
maybe_set_from_file OPENAI_WORKFLOW_ID "$ENV_FILE"

OPENAI_API_KEY="${OPENAI_API_KEY:-}"
if [[ -z "$OPENAI_API_KEY" ]]; then
    echo "OPENAI_API_KEY is not set" >&2
    exit 2
fi

OPENAI_WORKFLOW_ID="${OPENAI_WORKFLOW_ID:-}"
if [[ -z "$OPENAI_WORKFLOW_ID" ]]; then
    echo "OPENAI_WORKFLOW_ID is not set" >&2
    exit 3
fi

OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
OPENAI_BASE_URL="${OPENAI_BASE_URL%/}"

PAYLOAD=$(OPENAI_WORKFLOW_ID="$OPENAI_WORKFLOW_ID" WORKFLOW_MESSAGE="$MESSAGE" python - <<'PY'
import json
import os

workflow_id = os.environ["OPENAI_WORKFLOW_ID"].strip()
message = os.environ.get("WORKFLOW_MESSAGE", "ping")
payload = {
    "workflow_id": workflow_id,
    "inputs": {
        "message": message,
    },
}
print(json.dumps(payload, ensure_ascii=False))
PY
)

if [[ -z "$PAYLOAD" ]]; then
    echo "Failed to build JSON payload" >&2
    exit 4
fi

curl_args=(
    -sS
    -X POST
    "${OPENAI_BASE_URL}/workflows/runs"
    -H "Authorization: Bearer ${OPENAI_API_KEY}"
    -H "Content-Type: application/json"
    -H "OpenAI-Beta: workflows=v1"
    -d "$PAYLOAD"
)

if [[ -n "${OPENAI_PROJECT:-}" ]]; then
    curl_args+=( -H "OpenAI-Project: ${OPENAI_PROJECT}" )
fi

if [[ -n "${OPENAI_ORG:-}" ]]; then
    curl_args+=( -H "OpenAI-Organization: ${OPENAI_ORG}" )
fi

curl "${curl_args[@]}"

printf '\n'
