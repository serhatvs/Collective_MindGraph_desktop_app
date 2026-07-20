#!/usr/bin/env bash
# Start the desktop application in development mode.
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

echo "--- Collective MindGraph Desktop Startup ---"
export PYTHONPATH="$REPO_ROOT/src:$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

if [ -x "$REPO_ROOT/realtime_backend/.venv/bin/python" ]; then
    PYTHON_EXEC="$REPO_ROOT/realtime_backend/.venv/bin/python"
else
    echo "Warning: .venv not found. Using system python."
    PYTHON_EXEC="python3"
fi

echo "python=$PYTHON_EXEC"
echo "PYTHONPATH=$PYTHONPATH"
echo "UI_MODE=REBUILT_NATIVE_MVP_UI"

exec "$PYTHON_EXEC" -m collective_mindgraph_desktop
