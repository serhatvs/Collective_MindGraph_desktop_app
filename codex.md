# codex.md

## Project
- Name: Collective MindGraph
- Type: Native Windows-first desktop application
- Stack: Python 3.11+, PySide6, SQLite
- Philosophy: Local-first, offline-capable, privacy-focused.

## Current State
- **Architecture**: Transitions to a strictly local-first design. All cloud AI providers (Amazon Bedrock, Deepgram) have been removed.
- **Desktop UI**: `src/collective_mindgraph_desktop` provides a `QMainWindow` with session explorer, voice command panel, and session detail view.
- **Backend**: `realtime_backend` FastAPI service handles transcription and LLM correction using local-only providers. Diarization is planned for future release.
- **Transcription**: Uses `faster-whisper` (local) for STT and `silero-vad` for voice activity detection.
- **LLM Correction**: Defaults to `lmstudio` or other OpenAI-compatible local endpoints for transcript cleanup.
- **Diarization**: (Roadmap) Automatic speaker separation is not currently implemented or validated.
- **V2 Architecture**: A spreadsheet-driven V2 scaffold is under development in `src/collective_mindgraph` to formalize domain boundaries.
- **Packaging**: Supports single-file Windows builds via PyInstaller, bundling the local backend (using lighter fallbacks for VAD instead of the full `pyannote`/`torch` stack).

## Removed Features
- **Cloud STT**: Deepgram Nova-3 integration removed.
- **Cloud LLM**: Amazon Bedrock / Amazon Nova support removed.
- **External Dependencies**: `boto3`, `botocore`, and other cloud SDKs removed.

## Future Tasks
- [ ] Add real Turkish audio fixture test for Faster-Whisper language forcing.
- [ ] Formalize V2 domain implementations following the spreadsheet-driven architecture.
- [ ] Improve local diarization stability for 3+ speakers.
- [ ] Optimize onefile build size for full local model distribution.
