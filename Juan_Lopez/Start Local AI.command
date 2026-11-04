#!/bin/zsh
set -e
ATSC_PROJECT_DIR="${0:A:h}"
cd "$ATSC_PROJECT_DIR"
"$ATSC_PROJECT_DIR/backend/.venv/bin/python" "$ATSC_PROJECT_DIR/backend/scripts/start_local_ai.py"
