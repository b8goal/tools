#!/usr/bin/env bash
# Common utilities for Signal Finder MCP launcher scripts.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

# Load .env file into environment (does NOT override existing vars)
load_env() {
  if [[ -f "$ENV_FILE" ]]; then
    while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
      [[ -z "$raw_line" ]] && continue
      [[ "$raw_line" == \#* ]] && continue
      [[ "$raw_line" != *=* ]] && continue

      local key="${raw_line%%=*}"
      local value="${raw_line#*=}"

      # Strip surrounding quotes
      if [[ "$value" == \"*\" && "$value" == *\" ]]; then
        value="${value:1:${#value}-2}"
      elif [[ "$value" == \'*\' ]]; then
        value="${value:1:${#value}-2}"
      fi

      # Only export if not already set
      if [[ -z "${!key:-}" ]]; then
        export "$key=$value"
      fi
    done < "$ENV_FILE"
  fi
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ Missing required command: $cmd" >&2
    exit 1
  fi
}
