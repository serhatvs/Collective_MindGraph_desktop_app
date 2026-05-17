# Collective MindGraph

Collective MindGraph is a native Windows-first desktop application built with Python, PySide6, and SQLite. The desktop app stays local-first for session storage, and its voice transcription flow now connects to the sibling `realtime_backend/` FastAPI service for local, multi-speaker speech-to-text with privacy-focused offline processing.

## Cloud AI providers removed
- Amazon Bedrock / Nova support was removed.
- Deepgram (online ASR) support was removed.
- The project now expects local/offline providers only.
- Old environment variables (AWS, Deepgram) should be deleted.
- Users should configure local providers (e.g., faster-whisper, LM Studio).

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
- Local STT path through local `faster-whisper` inside the backend
- Editable transcript-segment correction UI for speaker labels and corrected text

## Product-integration ready for local-first Turkish transcription
Real meeting-room production accuracy still requires project-specific/manual meeting audio validation.

## Project Documentation
- **[PROJECT_STATUS.md](PROJECT_STATUS.md)**: Current MVP summary, implementation matrix, and honest claim boundaries.
- **[HANDOFF.md](HANDOFF.md)**: Technical overview and architecture details for developers.
- **[DEMO_FLOW.md](DEMO_FLOW.md)**: Step-by-step instructions for demonstrating the product loop.
- **[TECHNICAL_OVERVIEW_FOR_PATENT.md](TECHNICAL_OVERVIEW_FOR_PATENT.md)**: Conceptual and technical summary suitable for external reference/filing.
- **[DEMO_PRESENTATION_NOTES.md](DEMO_PRESENTATION_NOTES.md)**: Structured scripts for short and technical demonstrations.
- **[V2_ROADMAP.md](V2_ROADMAP.md)**: 4-phase plan for future development from MVP to hardware-integrated semantic system.

### Extraction Output Example (Turkish)
For a session containing: *“Merhaba, bugün Collective MindGraph toplantısındayız. Bu hafta FastAPI endpointini test edeceğiz.”*

The system extracts:
- **Summary**: `1 speaker covered Action Items. Early context: Merhaba, bugün Collective MindGraph toplantısındayız...`
- **Tasks**:
  - `title`: "Bu hafta fastapi endpointini test edeceğiz"
  - `responsible_person`: "Speaker_1"
  - `source_segment_id`: "s1"
- **Topics**: `["Action Items", "FastAPI", "MindGraph"]`
- **People**: `["Speaker_1"]`

### Memory Graph Status
Collective MindGraph currently uses **basic graph-node persistence** via hierarchical nodes in SQLite (adjacency list with `parent_node_id`). It is not a full graph database; it supports tree-based exploration and side-node enrichment for tasks and decisions.
## Desktop Global Search status
- **implemented**: local keyword memory search UI in the "Memory Search" panel
- **searches**: transcripts, tasks, decisions, and topics across all sessions
- **source-linked**: results allow double-clicking to navigate back to the source session and segment
- **semantic/vector search**: future TODO
- **full graph reasoning**: not implemented yet; uses basic hierarchical node structure

## Current memory/query status
...
- **implemented**: local keyword search over cleaned transcripts, tasks, decisions, topics
- **implemented**: source-linked query results
- **implemented**: basic heuristic scoring (prioritizing decisions and tasks)
- **not implemented yet**: vector embeddings, semantic search, arbitrary graph edges, multi-hop reasoning
- **current graph storage**: SQLite adjacency/tree-style nodes, not full graph database

## Local Demo Flow

To explore the integrated system locally:

1.  **Install dependencies**:
    ```powershell
    python -m pip install -e .
    cd realtime_backend
    python -m venv .venv
    .\.venv\Scripts\activate
    pip install -r requirements.txt
    ```

2.  **Start the Backend**:
    ```powershell
    ./scripts/dev_backend.sh
    ```

3.  **Start the Desktop App**:
    ```powershell
    ./scripts/dev_desktop.sh
    ```

4.  **Seed a Demo Session (Optional)**:
    If you don't have audio ready, run:
    ```powershell
    PYTHONPATH=. python realtime_backend/scripts/seed_demo_session.py
    ```

5.  **Explore the Product Loop**:
    - **Transcribe**: Record a technical session or transcribe a local file.
    - **Inspect**: Compare **Raw ASR** vs. **Cleaned Transcript** in the session detail.
    - **Memory**: View extracted tasks, decisions, and topics.
    - **Search**: Open **Global Search**, enter technical terms, and double-click to navigate back to the source.

## Current Implementation Status

### Implemented
- **Local transcription pipeline**: 100% offline Faster-Whisper with CPU/GPU support.
- **Raw/clean transcript separation**: Preserves original ASR output and cleaned text.
- **Turkish clean-speech benchmark**: Verified with Common Voice dataset (91% score).
- **Structured extraction**: Heuristic-based extraction of tasks, decisions, and topics.
- **Basic graph-node persistence**: Hierarchical storage of meeting knowledge in SQLite.
- **Keyword memory search**: Cross-session traceable lookup via `/query` API.
- **Desktop Global Search**: Integrated UI for cross-session knowledge retrieval.

### Pending
- **Project-specific meeting audio validation**: Infrastructure ready; pending manual recording.
- **Semantic/Vector search**: Interface placeholders added; implementation pending.
- **Full graph edge reasoning**: Current storage is hierarchical tree only.
- **Production diarization validation**: Verified for 1-2 speakers; high-noise stability pending.

## Installation
...
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

## Tech Stack

- **Desktop UI**: PySide6 (Qt)
- **Backend API**: FastAPI
- **ASR**: `faster-whisper` (local)
- **VAD**: `silero-vad` (local)
- **Diarization**: `pyannote.audio` (local)
- **Memory Persistence**: SQLite (Hierarchical graph-node storage)
- **LLM Cleanup**: Local API (LM Studio, Ollama)
- **Database**: SQLite3 (Desktop) / File-based (Backend)
- **Audio**: sounddevice / soundfile / ffmpeg

Notes:

- If `ffmpeg` is available on the build machine, the build script bundles it into the `.exe`.
- To stay within PyInstaller's onefile size limit, the bundled backend uses lighter built-in
  fallbacks for VAD/diarization instead of packaging the full `pyannote`/`torch` stack.
- Cloud-backed transcription or correction providers are no longer supported.

## Test

```powershell
python -m pytest
```
