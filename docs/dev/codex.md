# Codex Repository Memory

## Project

- Collective MindGraph is a Windows-first, local-first Python desktop application.
- Primary stack: Python 3.11+, PySide6, FastAPI, SQLite, Faster-Whisper, and optional local AI providers.
- Product claims must remain conservative: diarization/speaker separation is roadmap work; local LLM and real semantic embeddings are optional; confidence estimates are not accuracy or WER/CER.

## Current State

- Active maintenance branch: `refactor/engineering-cleanup`, created from `feature/transcription-reference-tooling` at `291637e966ed08fca1d1f394012b1e64c42fb590`.
- The cleanup preserves the transcription, memory, persistence, API, WebSocket, and desktop boundaries. No cloud services, models, UI features, or product redesign were added.
- Default pytest discovery includes both `tests/` and `realtime_backend/tests/`.
- Generated/local state at repository root is ignored, including `.venv-win/`, `models/`, `realtime_backend_temp/`, `realtime_backend_data/`, and `transcription_settings.json`.
- `transcription_settings.json` and the seeded demo transcript remain available locally but are no longer tracked.

## Architecture

- Desktop ownership: `src/collective_mindgraph_desktop/` handles UI, recording, backend transport, desktop persistence, and response parsing.
- Backend ownership: `realtime_backend/app/` handles configuration, preprocessing, VAD, ASR, selective retranscription, transcript formatting, streaming, HTTP APIs, and backend persistence.
- Evaluation ownership: `realtime_backend/app/evaluation/transcription_metrics.py` is authoritative for reference-based WER/CER/edit-distance evaluation.
- Glossary ownership: `realtime_backend/app/pipeline/transcription_glossary.py` owns glossary-file loading and resolution.
- Audio executable ownership: `realtime_backend/app/utils/audio_process.py` owns FFmpeg resolution.
- Runtime diagnostics are exposed through an immutable transcription runtime snapshot; callers must not reach into pipeline/provider private fields.
- File and WebSocket transcript payloads are built by `realtime_backend/app/pipeline/transcript_formatter.py`.

## Verified Behavior

- Cleanup baseline: focused transcription suite `157 passed, 2 skipped`; original root-only suite `239 passed, 3 skipped`.
- Recovery verification: focused surviving-change suite `95 passed, 1 skipped, 1 warning`; unified offscreen suite `367 passed, 5 skipped, 5 warnings` in `66.03s` on Python `3.13.14`.
- Optional skips are the unavailable local LLM, unavailable configured real embedding model, and two missing project-specific Turkish meeting fixtures.
- Remaining warnings are one Starlette TestClient deprecation and four `torch.jit.load` deprecations.
- A cached Faster-Whisper `small` CPU smoke on `cv_tr_000.wav` returned `ASR_STATUS=OK`, provider `faster_whisper`, one segment, and no mock fallback.
- The full suite no longer modifies tracked simulation reports.

## Durable Decisions

- Do not silently change transcription profiles, model/device defaults, VAD/preprocessing thresholds, selective retranscription defaults, fallback behavior, or persisted schemas.
- Keep raw, selected, and cleaned transcript data distinct; keep reference metrics distinct from heuristic confidence.
- Keep ASR provider, preprocessing, orchestration, evaluation, persistence, API, and desktop boundaries even when similar models exist across layers.
- Do not commit real meeting audio, personal device identifiers, model weights, local databases, generated exports, or machine-specific paths.
- Preserve benchmark evidence and dated reports that support project claims.

## Deferred Risks

- Equivalent memory/provider modules exist in desktop/core and backend trees, but source-mode isolation and persistence ownership make consolidation risky without a dedicated migration plan.
- `llm_provider="disabled"` is inconsistent with the LLM builder's unknown-value fallback to LM Studio. Preserve current behavior until configuration semantics are explicitly migrated and tested.
- Environment/config naming remains partly duplicated across legacy `CMG_*` and `CMG_RT_*` aliases; external compatibility prevents silent removal.
- Candidate scoring, confidence estimation, and some timeline helpers are related but not behaviorally identical; do not merge them based on naming alone.
- Dependency declarations are broad and environment versions drift, but no runtime dependency was proven removable in this cleanup.
- Real meeting-room Turkish WER/CER, Silero behavior on the target Windows runtime, packaging, and installer validation remain open validation work.

## Next Likely Tasks

- Gather human-reviewed, representative Turkish meeting audio before tuning ASR or reporting accuracy.
- Resolve the LLM disabled/default contradiction through an explicit compatibility plan.
- Validate packaging and launch flows on the target tester machine.
- Treat any further memory-layer consolidation as a separate persistence-aware project.
