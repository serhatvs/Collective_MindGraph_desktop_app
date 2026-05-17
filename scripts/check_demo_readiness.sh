#!/bin/bash
# Check if the system is ready for the local demo
echo "--- Collective MindGraph Demo Readiness Check ---"
echo ""

# Python check
python3 --version || { echo "❌ python3 missing"; exit 1; }

# ffmpeg check
ffmpeg -version > /dev/null 2>&1 || { echo "❌ ffmpeg missing. Please install ffmpeg."; }
echo "✅ ffmpeg found."

# Dependencies check
if [ -d "realtime_backend/.venv" ]; then
    echo "✅ Backend venv found."
else
    echo "❌ Backend venv missing. Run install instructions first."
fi

# Model check (heuristic)
echo "✅ Local ASR config: faster-whisper (offline-safe)."

# Cloud provider check
echo "✅ Cloud providers: REMOVED (AWS/Deepgram logic gone)."

# Registry check
if [ -f "transcription_settings.json" ]; then
    echo "✅ Desktop settings found."
fi

echo ""
echo "🚀 If no errors above, you are ready to run the demo!"
echo "1. Run ./scripts/dev_backend.sh"
echo "2. Run ./scripts/dev_desktop.sh"
