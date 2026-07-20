# Collective MindGraph Demo / Packaging Quickstart

## Purpose

This quickstart is the authoritative Windows-first guide for running a clean Collective MindGraph demo from `main`-based demo/packaging work.

It documents the current verified demo baseline, the manual launch path, the known packaging state, and the claim boundaries that must stay visible during demo preparation.

## Verified Baseline

- Baseline branch: `feature/demo-packaging-polish`, created from clean `origin/main`.
- Memory Track baseline: focused tests passed with `38 passed`.
- Stable checkpoint tag: `memory-track-main-validated-2026-07-02`.
- Verified package/installer: none.
- Current readiness focus: demo setup, packaging documentation, and UI polish readiness. Core Memory Track behavior is not the known blocker.

## Scope Boundaries

- This branch is for demo, packaging, and UI polish readiness only.
- The paused transcription work remains on `feature/transcription-quality-pipeline`.
- Do not use this branch for transcription quality work.
- Do not change ASR, audio, VAD, Faster-Whisper, diarization, or meeting-room transcription behavior as part of this phase.
- Diarization is not implemented or validated as a product feature.
- Speaker separation is roadmap and must not be claimed as ready.
- Local LLM support is optional and fallback-first; do not claim always-active LLM reasoning.
- No production installer or signed package is currently verified.

## Recommended Windows Demo Setup

Use PowerShell and run the backend and desktop in separate terminals.

Recommended repository path for this demo worktree:

```powershell
D:\Workspace\cmg-main-test
```

Recommended Python runtime used for the current Windows validation:

```powershell
D:\Workspace\Collective-MindGraph-2\.venv-win\Scripts\python.exe
```

Before demoing, confirm the branch and working tree:

```powershell
cd D:\Workspace\cmg-main-test
git status --short --branch
```

Expected branch:

```text
## feature/demo-packaging-polish...origin/main
```

## Backend Launch

Recommended helper:

```powershell
cd D:\Workspace\cmg-main-test\realtime_backend
.\scripts\run_dev.ps1
```

Manual fallback:

Start the FastAPI backend from the backend source directory:

```powershell
cd D:\Workspace\cmg-main-test\realtime_backend
$env:PYTHONPATH='.;..\src'
D:\Workspace\Collective-MindGraph-2\.venv-win\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Useful local health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

## Desktop Launch

Recommended helper:

```powershell
cd D:\Workspace\cmg-main-test
.\scripts\launch\dev_desktop.ps1
```

Manual launch for debugging:

Start the native PySide6 desktop app from the repository root:

```powershell
cd D:\Workspace\cmg-main-test
$env:PYTHONPATH='src;.'
D:\Workspace\Collective-MindGraph-2\.venv-win\Scripts\python.exe -m collective_mindgraph_desktop
```

The desktop app is the user-facing UI. The FastAPI `/docs` page is only for developer debugging.

## Backend Port Choice

Use port `8080` for the manual Windows demo flow.

Reason: backend defaults, embedded backend launch behavior, and the desktop default transcription config align around `http://127.0.0.1:8080`.

Known inconsistency: some helper scripts and older docs mention `8081`. This quickstart standardizes the manual demo flow on `8080` until scripts and docs are harmonized in a later patch.

If you intentionally use another port, update the desktop transcription backend URL in the app settings or set:

```powershell
$env:CMG_TRANSCRIPTION_BACKEND_URL='http://127.0.0.1:8080'
```

## Database Locations

Desktop default SQLite location:

```text
%LOCALAPPDATA%\CollectiveMindGraph\collective_mindgraph.sqlite3
```

Backend default SQLite location when launched from `D:\Workspace\cmg-main-test\realtime_backend`:

```text
D:\Workspace\cmg-main-test\realtime_backend\realtime_backend_data\collective_mindgraph.sqlite3
```

Frozen embedded backend default data location:

```text
%LOCALAPPDATA%\CollectiveMindGraph\realtime_backend_data\collective_mindgraph.sqlite3
```

Important risk: desktop and backend may point at different SQLite files. That can make seeded data, Ask Memory results, and backend query results appear inconsistent.

Demo recommendation:

- Prefer one end-to-end flow through the desktop UI when possible.
- If backend query/Ask endpoints must see the same graph state as the desktop, explicitly align `CMG_RT_DATA_DIR` or verify that the same data appears in both the UI and backend flow.
- After seeding or importing data, verify that Ask Memory evidence-only returns expected demo evidence before presenting.

## Optional Embedding Settings

Default behavior is fallback/mock-first. The app can run without real local embeddings.

Real semantic retrieval requires explicit local model configuration. Do not rely on implicit remote downloads for demos.

Example local-only PowerShell setup:

```powershell
$env:CMG_EMBEDDINGS_ENABLED='true'
$env:CMG_EMBEDDING_PROVIDER='sentence_transformers'
$env:CMG_EMBEDDING_MODEL_PATH='D:\Models\paraphrase-multilingual-MiniLM-L12-v2'
$env:CMG_EMBEDDING_DIMENSION='384'
$env:CMG_ALLOW_REMOTE_MODEL_DOWNLOAD='false'
```

If no local embedding model is configured, the system should remain usable through keyword, graph, and evidence-only memory behavior.

## Optional Local LLM Settings

Collective MindGraph is fallback-first. Evidence-only Ask Memory works without a local LLM.

Optional local LLM runtimes may include LM Studio or Ollama when exposed through a local/OpenAI-compatible endpoint. These are optional enhancements, not required for the baseline demo.

Example LM Studio-style local endpoint:

```powershell
$env:CMG_LOCAL_LLM_PROVIDER='lmstudio'
$env:CMG_LOCAL_LLM_ENDPOINT='http://127.0.0.1:1234/v1'
$env:CMG_ALLOW_REMOTE_ACCESS='false'
```

Recommended demo posture:

- Use Evidence Only mode first.
- Treat LLM-assisted Ask Memory as optional.
- If the LLM is unavailable or produces unsupported content, the system may reject the LLM answer and fall back to evidence-only behavior.

## Demo Flow

1. Start the backend on port `8080`.
2. Start the desktop app.
3. Seed the technical demo if available:

```powershell
cd D:\Workspace\cmg-main-test
$env:PYTHONPATH='src;.'
D:\Workspace\Collective-MindGraph-2\.venv-win\Scripts\python.exe realtime_backend\scripts\seed_demo_session.py
```

4. In the desktop app, open or create a memory session.
5. Review the session through:
   - `Knowledge Audit`
   - `Reviewed Memory`
   - `Review Suggestions`
   - `Knowledge Graph`
6. Open `Global Search`.
7. Use `Ask Your Memory` in `Evidence Only` mode first.
8. Ask a demo query such as:

```text
FastAPI ile ilgili görevler neler?
```

9. Export the session as JSON.
10. Import the exported JSON.
11. Reopen the imported session and verify its reviewed memory, graph data, and source-linked evidence.
12. Open `Diagnostics` and confirm the visible runtime state before presenting claims.

## Export / Import Flow

Export:

1. Select a memory session in the desktop app.
2. Open `File > Export Knowledge`.
3. Save the JSON file.

Import:

1. Open `File > Import Knowledge`.
2. Select the exported JSON file.
3. Confirm that the imported session appears in the session list.
4. Open the imported session and verify transcript, reviewed memory, graph entries, and evidence links.

The current Memory Track tests validate export/import roundtrip behavior for the focused memory scope, but this is not the same as a production backup/restore certification.

## Diagnostics

Open the `Diagnostics` tab in the desktop app before a demo.

Use it to check:

- Backend reachability.
- ASR/runtime status.
- VAD provider status.
- Embedding provider and vector count.
- Local LLM status.
- Ask Memory evidence-only and LLM-assisted status.
- Diarization status boundary.

Do not present diagnostics as proof of production packaging or production meeting-room transcription quality.

## Packaging State

Related checklist: [Packaging Smoke Checklist](PACKAGING_SMOKE_CHECKLIST.md).

Verified packaging scaffold:

- `CollectiveMindGraph.spec`
- `scripts\packaging\build_windows_exe.ps1`
- `pyproject.toml` build optional dependency for PyInstaller

Current verified package state:

- PyInstaller scaffold exists.
- No production installer verified.
- No signed executable flow verified.
- No release checklist verified.
- No MSIX package verified.
- No Inno Setup installer verified.
- No NSIS installer verified.
- No production packaged runtime validation has been recorded in this branch.

Do not claim production packaging exists until a build artifact, installer flow, signing state, and packaged runtime smoke test are verified.

## Known Gaps Before Packaging

- Standardize all docs and helper scripts on one demo port.
- Add a Windows-first setup path for backend and desktop launch.
- Decide whether demo data should live in desktop storage, backend storage, or an explicitly shared path.
- Add a packaged-runtime smoke checklist.
- Verify PyInstaller output on a clean Windows machine.
- Decide whether model files are bundled, user-provided, or configured externally.
- Document expected behavior when embeddings or local LLM are absent.
- Add installer/signing/release checklist only after choosing the packaging technology.

## Validation Checklist

- `git status --short --branch` was clean before this documentation patch.
- Focused Memory Track tests still pass if run.
- Backend starts on `127.0.0.1:8080`.
- Desktop starts with `python -m collective_mindgraph_desktop`.
- Technical demo data can be seeded or opened.
- Ask Memory in Evidence Only mode responds from seeded/demo data.
- Export JSON works from the desktop UI.
- Import JSON works from the desktop UI.
- Diagnostics tab opens and displays runtime state.
- No installer claim was added.
- No production package claim was added.
