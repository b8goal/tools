#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$APP_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
REQUIREMENTS="$APP_DIR/requirements.txt"
REQUIREMENTS_STAMP="$VENV_DIR/.requirements.sha256"

cd "$APP_DIR"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "[keyboard_macro] Creating virtual environment: $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

if command -v shasum >/dev/null 2>&1; then
  CURRENT_REQUIREMENTS_HASH="$(shasum -a 256 "$REQUIREMENTS" | awk '{print $1}')"
else
  CURRENT_REQUIREMENTS_HASH="$(sha256sum "$REQUIREMENTS" | awk '{print $1}')"
fi

INSTALLED_REQUIREMENTS_HASH=""
if [ -f "$REQUIREMENTS_STAMP" ]; then
  INSTALLED_REQUIREMENTS_HASH="$(cat "$REQUIREMENTS_STAMP")"
fi

if [ "$CURRENT_REQUIREMENTS_HASH" != "$INSTALLED_REQUIREMENTS_HASH" ]; then
  echo "[keyboard_macro] Installing dependencies in .venv"
  "$PYTHON_BIN" -m pip install --upgrade pip
  "$PYTHON_BIN" -m pip install -r "$REQUIREMENTS"
  printf "%s" "$CURRENT_REQUIREMENTS_HASH" > "$REQUIREMENTS_STAMP"
fi

echo "[keyboard_macro] Launching app with $PYTHON_BIN"
exec "$PYTHON_BIN" "$APP_DIR/run_app.py"
