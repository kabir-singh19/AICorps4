#!/usr/bin/env bash
# ATSC road evaluator for macOS and Linux. First run creates demo/.venv and installs the packages.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
venv="$here/.venv"
if [ ! -f "$venv/.ready" ]; then
  py=""
  for c in python3.13 python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then py="$c"; break; fi
  done
  if [ -z "$py" ]; then echo "Python 3.11 or newer is required: https://www.python.org/downloads/"; exit 1; fi
  echo "First run: setting up a Python environment with $py (takes a minute)..."
  rm -rf "$venv"
  "$py" -m venv "$venv"
  "$venv/bin/python" -m pip install -q --upgrade pip
  "$venv/bin/python" -m pip install -q -r "$here/requirements.txt"
  if ! "$venv/bin/python" -c "import lightgbm" 2>/dev/null; then
    echo "LightGBM could not load. On a Mac run:  brew install libomp   then run this script again."
    exit 1
  fi
  touch "$venv/.ready"
fi
exec "$venv/bin/python" "$here/atsc_cmd.py"
