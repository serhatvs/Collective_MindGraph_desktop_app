#!/usr/bin/env bash
# Start the realtime transcription backend on port 8080.
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

echo "Starting Collective MindGraph Backend on port 8080..."
export PYTHONPATH="$REPO_ROOT/src:$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

cd "$REPO_ROOT/realtime_backend"
if [ -x ".venv/bin/python" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
else
    echo "Warning: .venv not found. Using system python."
fi

export CMG_RT_PORT=8080
export CMG_RT_ASR_DEVICE=${CMG_RT_ASR_DEVICE:-cpu}
export CMG_RT_ASR_COMPUTE_TYPE=${CMG_RT_ASR_COMPUTE_TYPE:-int8}
export CMG_RT_LANGUAGE=${CMG_RT_LANGUAGE:-tr}

exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
