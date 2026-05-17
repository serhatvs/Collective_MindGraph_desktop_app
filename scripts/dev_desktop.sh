#!/bin/bash
# Start the desktop application in development mode
echo "Starting Collective MindGraph Desktop..."
export PYTHONPATH=src:realtime_backend
python3 -m collective_mindgraph_desktop
