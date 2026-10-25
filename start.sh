#!/usr/bin/env bash
# One-shot start for macOS / Linux: create .venv if missing, install requirements, run the app.
# Usage: ./start.sh [--host HOST] [--port PORT] [--no-browser]   (or: bash start.sh ...)
set -euo pipefail
cd "$(dirname "$0")"

VERSION_OK='import sys; sys.exit(sys.version_info < (3, 10))'

venv_python() {
  if [ -x ".venv/bin/python" ]; then echo ".venv/bin/python";
  elif [ -x ".venv/Scripts/python.exe" ]; then echo ".venv/Scripts/python.exe";  # Git Bash on Windows
  fi
}

# A usable venv runs Python 3.10+ and has pip. A venv left by an older Python, or a half-built
# one (e.g. Debian/Ubuntu without python3-venv), is not reused: it would fail the same way forever.
venv_ok() {
  local py
  py="$(venv_python)"
  [ -n "$py" ] && "$py" -c "$VERSION_OK" >/dev/null 2>&1 && "$py" -m pip --version >/dev/null 2>&1
}

# The first interpreter on PATH that is Python 3.10 or newer (macOS ships 3.9 as python3).
find_python() {
  local candidate
  for candidate in python3 python3.14 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "$VERSION_OK" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if [ -e ".venv" ] && ! venv_ok; then
  echo "[setup] The existing .venv is broken or uses Python older than 3.10; recreating it ..."
  rm -rf .venv
fi

if [ ! -e ".venv" ]; then
  if ! PYTHON="$(find_python)"; then
    echo "[setup] Python 3.10 or newer is required: https://www.python.org/downloads/" >&2
    echo "[setup] Install it, then run ./start.sh again." >&2
    exit 1
  fi
  echo "[setup] Creating virtual environment in .venv with $("$PYTHON" -c 'import sys; print(sys.version.split()[0])') ..."
  if ! "$PYTHON" -m venv .venv || ! venv_ok; then
    rm -rf .venv
    echo "[setup] Could not create .venv (on Debian/Ubuntu: sudo apt install python3-venv), then run ./start.sh again." >&2
    exit 1
  fi
fi

PY="$(venv_python)"
echo "[setup] Installing requirements ..."
if ! "$PY" -m pip install -q --disable-pip-version-check -r requirements.txt; then
  echo "[setup] pip install failed. Check your internet connection, or delete the .venv folder and run ./start.sh again." >&2
  exit 1
fi
exec "$PY" run.py "$@"
