# Collective MindGraph

Collective MindGraph is a native Windows-first desktop application built with Python, PySide6, and SQLite. The desktop app stays local-first for session storage, and its voice transcription flow now connects to the sibling `realtime_backend/` FastAPI service for multi-speaker speech-to-text with online-first Deepgram transcription, Amazon Bedrock transcript correction, and local fallbacks.

## Features

- Native `QMainWindow` application with a modern Qt widget UI
- SQLite persistence created automatically on first launch
- Session explorer with search, create, delete, and detail view
- Transcript timeline, backend analysis panel, graph tree, and snapshot history panels
- Demo data seeding and deterministic snapshot rebuilding
- JSON export for a selected session
- Voice capture UI that records locally, auto-stops after a short silence, auto-transcribes through the local realtime backend, and continues or starts sessions ChatGPT-style
- Selectable microphone input in the voice settings dialog, persisted in `transcription_settings.json`
- Optional VOSK-based wake trigger that listens for `command wake` to start hands-free capture and `command shut` to cancel the active voice turn while the listener stays armed, while still tolerating common VOSK variants such as `command wake up` or `command shutdown`
- Configurable wake phrases, wake cooldown, live transcript streaming toggle, and auto-stop thresholds in the voice settings dialog
- Near-real-time transcript streaming from the growing local WAV capture into the backend WebSocket endpoint, with automatic fallback to final file upload if the stream path fails
- Backend runtime health in the desktop voice panel, including the resolved STT/LLM providers and any configured fallback chain
- Automatic local backend startup for the sibling `realtime_backend/` service when the desktop app is pointed at loopback and the backend is down
- Stronger transcript correction UX in the session detail view, including bulk speaker rename/merge, segment reordering, and merge-with-next editing
- Session graph enrichment from backend analysis so summary/topics and decisions/action items become side nodes beside the primary transcript node
- Online-first STT path through Deepgram Nova-3 with local `faster-whisper` fallback inside the backend
- Editable transcript-segment correction UI for speaker labels and corrected text

## Installation

```powershell
python -m pip install -e .
```

For voice transcription, also install and run the backend in `realtime_backend/`.

For hands-free wake phrases, install the desktop dependencies and place a VOSK model under
`wake_phrase_models/` or set `CMG_WAKE_PHRASE_MODEL_PATH`. English trigger phrases such as
`command wake` and `command shut` fit the current small English model better than Turkish trigger words, and
the wake listener now follows the selected microphone when that device can be matched on the
sounddevice side.

## Run

```powershell
python -m collective_mindgraph_desktop
```

If you want voice transcription from the desktop app, start the backend first:

```powershell
cd realtime_backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --port 8080
```

## Single-File Windows Build

To produce a single `.exe` that contains both the desktop UI and the local backend:

```powershell
.\scripts\build_windows_exe.ps1
```

The script prefers `realtime_backend\.venv\Scripts\python.exe`, installs the desktop package plus
`PyInstaller`, and writes the output to `dist\CollectiveMindGraph.exe`.

The packaged app starts its bundled local backend automatically on loopback and stores its
runtime settings/recordings under `%LOCALAPPDATA%\CollectiveMindGraph\`.

Notes:

- If `ffmpeg` is available on the build machine, the build script bundles it into the `.exe`.
- To stay within PyInstaller's onefile size limit, the bundled backend uses lighter built-in
  fallbacks for VAD/diarization instead of packaging the full `pyannote`/`torch` stack.
- In the packaged build, real STT depends on a configured Deepgram key; otherwise the backend falls
  back to its mock ASR path instead of shipping the full local model stack inside the `.exe`.
- Cloud-backed transcription or correction providers still need their normal API credentials at runtime.

## Test

```powershell
python -m pytest
```
