#!/bin/bash
# Start the realtime transcription backend on port 8081
echo "Starting Collective MindGraph Backend on port 8081..."
cd realtime_backend
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Warning: .venv not found. Using system python."
fi

export CMG_RT_PORT=8081
export CMG_RT_ASR_DEVICE=${CMG_RT_ASR_DEVICE:-cpu}
export CMG_RT_ASR_COMPUTE_TYPE=${CMG_RT_ASR_COMPUTE_TYPE:-int8}
export CMG_RT_LANGUAGE=${CMG_RT_LANGUAGE:-tr}

python -m uvicorn app.main:app --host 127.0.0.1 --port 8081 --reload
