#!/bin/bash
# Start the desktop application in development mode
echo "Starting Collective MindGraph Desktop..."
export PYTHONPATH=src:realtime_backend

if [ -f "realtime_backend/.venv/bin/python" ]; then
    PYTHON_EXEC="realtime_backend/.venv/bin/python"
else
    echo "Warning: .venv not found. Using system python."
    PYTHON_EXEC="python3"
fi

$PYTHON_EXEC -m collective_mindgraph_desktop
