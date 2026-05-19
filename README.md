# Collective MindGraph

Collective MindGraph is a native desktop application built with Python, PySide6, and SQLite. The **rebuilt native MVP UI** provides a modern, user-friendly interface for capturing technical technical conversations and building an automated organizational memory.

## Architecture

- **Primary Frontend**: Native PySide6 Desktop App (`src/`). Features a 3-area layout with tabbed functional navigation.
- **Local Backend**: FastAPI service (`realtime_backend/`) for 100% offline Turkish transcription and intelligence extraction.
- **Privacy First**: No cloud dependencies (AWS, Bedrock, and Deepgram have been removed).

## Core Features

- **Session Dashboard**: Overview of metadata, intelligence summaries, and organizational metrics.
- **Transcript Audit**: Side-by-side comparison of **Raw ASR output** and **Cleaned Technical Transcript**.
- **Intelligence Extraction**: Automated detection of Tasks (Action Items), Decisions, and Topics for Technical Turkish.
- **Global Memory Search**: Cross-session keyword search with direct source-segment navigation (Traceability).
- **Voice Ingest**: Local audio capture with automatic silence detection and local Faster-Whisper inference.
- **Diagnostics**: Real-time visibility into pipeline performance and offline safety status.

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
The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.

Real meeting-room production accuracy still requires project-specific/manual meeting audio validation.

## Project Documentation
- **[PROJECT_STATUS.md](PROJECT_STATUS.md)**: Current MVP summary, implementation matrix, and honest claim boundaries.
- **[HANDOFF.md](HANDOFF.md)**: Technical overview and architecture details for developers.
- **[DEMO_FLOW.md](DEMO_FLOW.md)**: Step-by-step instructions for demonstrating the product loop.
- **[PITCH_SUMMARY.md](PITCH_SUMMARY.md)**: Problem, solution, and value proposition at different lengths.
- **[PRESENTATION_PACKAGE_TR.md](PRESENTATION_PACKAGE_TR.md)**: Turkish presentation scripts and slide outline.
- **[DEMO_SCRIPT_TR.md](DEMO_SCRIPT_TR.md)**: Turkish presentation script for reviewers.
- **[DEMO_SCRIPT_EN.md](DEMO_SCRIPT_EN.md)**: English presentation script for technical partners.
- **[SLIDE_OUTLINE.md](SLIDE_OUTLINE.md)**: 7-slide structure for project presentations.
- **[TECHNICAL_QA.md](TECHNICAL_QA.md)**: Likely questions and honest, data-backed answers.
- **[PATENT_SAFE_CLAIMS.md](PATENT_SAFE_CLAIMS.md)**: Precise, non-overclaiming terminology for formal filings.
- **[TECHNICAL_OVERVIEW_FOR_PATENT.md](TECHNICAL_OVERVIEW_FOR_PATENT.md)**: Conceptual summary for external reference.
- **[V2_ROADMAP.md](V2_ROADMAP.md)**: 4-phase plan for future development.

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

### Memory Graph and Search Status
Collective MindGraph currently uses **basic graph-node persistence** via hierarchical nodes in SQLite (adjacency list with `parent_node_id`). It is not a full graph database; it supports tree-based exploration and side-node enrichment for tasks and decisions.

The backend provides a `/query` endpoint for **traceable local keyword search** over transcripts, tasks, decisions, and topics across all sessions. Semantic search and arbitrary graph edges are not yet implemented.

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

2.  **Verify environment**:
    ```powershell
    ./scripts/check_demo_readiness.sh
    ```

3.  **Seed a Demo Session**:
    If you don't have audio ready, run this to populate the memory:
    ```powershell
    PYTHONPATH=. python realtime_backend/scripts/seed_demo_session.py
    ```

4.  **Start the Backend**:
    ```powershell
    ./scripts/dev_backend.sh
    ```

5.  **Start the Desktop App**:
    ```powershell
    ./scripts/dev_desktop.sh
    ```

6.  **Explore the Product Loop**:

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
