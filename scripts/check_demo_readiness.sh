#!/usr/bin/env bash
# Check whether the local development demo has its required executables.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || exit 1

status=0
python_runtime=""

echo "--- Collective MindGraph Demo Readiness Check ---"
echo

if command -v python3 >/dev/null 2>&1; then
    python3 --version
    python_runtime="$(command -v python3)"
else
    echo "[MISSING] python3"
    status=1
fi

ffmpeg_override="${CMG_RT_FFMPEG_PATH:-${CMG_FFMPEG_EXE:-}}"
if [ -n "$ffmpeg_override" ] && [ -x "$ffmpeg_override" ]; then
    echo "[OK] ffmpeg override: $ffmpeg_override"
elif command -v ffmpeg >/dev/null 2>&1; then
    echo "[OK] ffmpeg found on PATH."
else
    echo "[MISSING] ffmpeg (install it or set CMG_RT_FFMPEG_PATH)."
    status=1
fi

if [ -x "realtime_backend/.venv/bin/python" ]; then
    echo "[OK] Backend virtual environment found."
    python_runtime="$REPO_ROOT/realtime_backend/.venv/bin/python"
else
    echo "[INFO] Backend virtual environment not found; checking system Python."
fi

if [ -n "$python_runtime" ] && "$python_runtime" -c "import fastapi, faster_whisper, PySide6" >/dev/null 2>&1; then
    echo "[OK] Core backend, ASR, and desktop dependencies are importable."
else
    echo "[MISSING] Core Python dependencies; run the documented dependency installer."
    status=1
fi

echo "[INFO] Local ASR: faster-whisper; remote model downloads are disabled by default."
echo "[INFO] Cloud providers: removed."
echo "[INFO] Diarization: roadmap only; disabled by default."

if [ -f "transcription_settings.json" ]; then
    echo "[INFO] Local desktop settings found (ignored by Git)."
fi

echo
if [ "$status" -ne 0 ]; then
    echo "Readiness check failed. Resolve the missing requirements above."
    exit "$status"
fi

echo "Readiness check passed."
echo "1. Run ./scripts/dev_backend.sh"
echo "2. Run ./scripts/dev_desktop.sh"
