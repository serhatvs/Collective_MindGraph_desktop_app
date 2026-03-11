# Collective MindGraph

Collective MindGraph is a native Windows-first desktop application built with Python, PySide6, and SQLite. The desktop app stays local-first for session storage, and its voice transcription flow now connects to the sibling `realtime_backend/` FastAPI service for multi-speaker speech-to-text.

## Features

- Native `QMainWindow` application with a modern Qt widget UI
- SQLite persistence created automatically on first launch
- Session explorer with search, create, delete, and detail view
- Transcript timeline, graph tree, and snapshot history panels
- Demo data seeding and deterministic snapshot rebuilding
- JSON export for a selected session
- Voice capture UI that can send recorded audio to the local realtime transcription backend

## Installation

```powershell
python -m pip install -e .
```

For voice transcription, also install and run the backend in `realtime_backend/`.

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

## Test

```powershell
python -m pytest
```
