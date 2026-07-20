# Collective MindGraph Packaging Smoke Checklist

## Purpose

This checklist is for validating future packaged Collective MindGraph artifacts. It is a smoke-test guide only.

It does not claim that production packaging, an installer, signing, or release automation currently exists.

## Current Packaging Status

- PyInstaller scaffold/spec exists: `CollectiveMindGraph.spec` and `scripts\packaging\build_windows_exe.ps1`.
- No production installer is verified.
- No signing flow is verified.
- No release checklist was verified before this document.
- No MSIX, Inno Setup, or NSIS package is verified.
- This document is only a smoke checklist for future packaged artifacts.

## Scope Boundaries

- This branch is for demo, packaging, and UI polish readiness.
- The transcription branch remains paused.
- No ASR, audio, VAD, Faster-Whisper, or diarization work is included here.
- Diarization and speaker separation are not implemented or validated as product features.
- This checklist must not be used as evidence that production packaging exists.

## Pre-Build Checks

- Confirm the working tree is clean:

```powershell
git status --short --branch
```

- Confirm the branch is the intended demo/packaging branch.
- Confirm the focused Memory Track tests pass, or record why they were intentionally skipped.
- Confirm active demo/backend references standardize on port `8080`.
- Confirm docs do not claim a production installer, signing flow, or release package exists.
- Confirm no ASR/audio/VAD/Faster-Whisper/diarization files are included in the packaging patch.

## Build Artifact Checks

- Packaged executable exists.
- Artifact name and version are visible if available.
- Artifact launches without Python console errors.
- Missing DLL errors are recorded.
- Missing model errors are recorded.
- Missing configuration errors are recorded.
- Any antivirus, Windows SmartScreen, or permission prompts are recorded.

Do not invent or assume a production artifact path. Record the actual path produced by the build under test.

## First Launch Checks

- Desktop window opens.
- App does not crash on startup.
- Backend connection status is visible.
- Diagnostics page opens.
- No browser page is mistaken for the product frontend.
- Startup logs, if present, do not show fatal import or path errors.

## Backend Runtime Checks

- Backend starts, or embedded backend starts.
- Backend binds to `127.0.0.1`.
- Expected demo port is `8080`.
- `/health` responds if the backend is reachable.
- `/docs` may exist as a developer/debug API page, but it is not the product UI.
- If backend startup fails, record the exact error and packaged log path.

## Desktop UI Checks

- Native PySide6 desktop is the product UI.
- Main window opens.
- Session explorer is visible.
- Voice ingest/header area is visible.
- Main tabs/pages open, including:
  - `Session Memory`
  - `Knowledge Audit`
  - `Reviewed Memory`
  - `Review Suggestions`
  - `Knowledge Graph`
  - `Reasoning Trace`
  - `Global Search`
  - `Diagnostics`
- UI text does not imply installer/signing/release readiness.

## Demo Data Checks

- Seeded or imported demo data appears in the desktop session list.
- A demo session can be opened.
- Transcript/audit content is visible.
- Reviewed memory content is visible.
- Knowledge graph rows or details are visible.
- Source navigation works where demo data includes source references.

## Ask Memory Checks

- Evidence-only mode is tested first.
- Evidence-only response cites or displays supporting evidence.
- LLM-assisted mode is optional only.
- If LLM-assisted mode is tested, record whether it is active, unavailable, rejected, or falling back.
- Fallback behavior is recorded.
- No unsupported claim should appear without source evidence.

## Export / Import Checks

- Export JSON is created from the desktop UI.
- Export path is recorded.
- Import JSON is accepted by the desktop UI.
- Imported session appears in the session list.
- Imported data is visible and searchable.
- Imported Ask Memory evidence works if matching source data exists.
- No manual database editing is required.

## Diagnostics Checks

- Diagnostics page opens.
- Backend URL/status is visible.
- ASR/runtime status is visible.
- VAD provider status is visible.
- Embedding provider/status is visible.
- Local LLM status is visible.
- Ask Memory evidence-only status is visible.
- Diarization/speaker separation status is not presented as implemented or validated.

## Database Path Checks

- Record where the packaged app stores SQLite data.
- Record where the backend stores SQLite data.
- Verify backend and desktop are reading the expected data.
- Record any mismatch if backend and desktop use different SQLite files.
- Verify export/import can move demo state without manual database edits.

## Offline / Fallback Checks

- App still demonstrates the core memory flow without LM Studio or Ollama.
- Evidence-only Ask Memory works without a local LLM when demo data is present.
- Embeddings may be mock/fallback unless a local model is explicitly configured.
- No cloud dependency is required for the baseline demo.
- Any remote access or remote download setting must be explicitly recorded if enabled.

## Packaging Gaps Not Yet Solved

- Installer technology is not selected.
- Signing is not configured.
- Update flow is not configured.
- Release artifact validation is not automated.
- Packaged runtime database alignment needs verification.
- Model bundling strategy is not finalized.
- Clean-machine packaged runtime testing is not yet recorded.

## Pass / Fail Template

| Area | Check | Result | Notes |
| --- | --- | --- | --- |
| Pre-build | Working tree clean on intended branch |  |  |
| Pre-build | Focused Memory Track tests pass or skip reason recorded |  |  |
| Build artifact | Packaged executable exists |  |  |
| Build artifact | Missing DLL/model/config errors recorded |  |  |
| First launch | Desktop opens without crash |  |  |
| Backend runtime | Backend binds to `127.0.0.1:8080` |  |  |
| Desktop UI | Native PySide6 UI is used as product frontend |  |  |
| Demo data | Demo/imported session opens |  |  |
| Ask Memory | Evidence-only answer responds with source evidence |  |  |
| Export/import | Export JSON created and imported |  |  |
| Diagnostics | Diagnostics page opens and status is visible |  |  |
| Database paths | Desktop/backend SQLite paths recorded |  |  |
| Offline/fallback | Core demo works without local LLM |  |  |
| Claim boundary | No installer/signing/production package claim added |  |  |
