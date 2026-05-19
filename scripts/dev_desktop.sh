#!/bin/bash
# Start the desktop application in development mode
echo "--- Collective MindGraph Desktop Startup ---"
export PYTHONPATH=src:realtime_backend

if [ -f "realtime_backend/.venv/bin/python" ]; then
    PYTHON_EXEC="realtime_backend/.venv/bin/python"
else
    echo "Warning: .venv not found. Using system python."
    PYTHON_EXEC="python3"
fi

echo "python=$PYTHON_EXEC"
echo "PYTHONPATH=$PYTHONPATH"
echo "UI_MODE=REBUILT_NATIVE_MVP_UI"

$PYTHON_EXEC -m collective_mindgraph_desktop
