#!/usr/bin/env bash
# Launch Playwright MCP server for Signal Finder.
# Enables JS-rendered page scraping (e.g., Clien, dynamic boards).
#
# Usage (stdio - used by codex/claude/antigravity):
#   ./scripts/mcp/run_playwright_mcp.sh
#
# The server exposes browser automation tools:
#   - playwright_navigate, playwright_click, playwright_fill
#   - playwright_screenshot, playwright_get_text, etc.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

load_env
require_command npx

NPX_BIN="${NPX_BIN:-/opt/homebrew/bin/npx}"

# --headless: run without visible browser window (default for CI/automation)
# Remove --headless if you want to see the browser during debugging
exec "$NPX_BIN" -y @playwright/mcp@latest --headless "$@"
