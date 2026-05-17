#!/bin/bash
# Start the realtime transcription backend in development mode
echo "Starting Collective MindGraph Backend..."
cd realtime_backend
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Warning: .venv not found. Using system python."
fi

# Development overrides for easier local testing
export CMG_RT_ASR_DEVICE=${CMG_RT_ASR_DEVICE:-cpu}
export CMG_RT_ASR_COMPUTE_TYPE=${CMG_RT_ASR_COMPUTE_TYPE:-int8}
export CMG_RT_LANGUAGE=${CMG_RT_LANGUAGE:-tr}

python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
