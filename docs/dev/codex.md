# Codex Repository Memory

## Project

- Collective MindGraph is a Windows-first, local-first Python desktop application.
- Primary stack: Python 3.11+, PySide6, FastAPI, SQLite, Faster-Whisper, and optional local AI providers.
- Product claims must remain conservative: diarization/speaker separation is roadmap work; local LLM and real semantic embeddings are optional; confidence estimates are not accuracy or WER/CER.

## Current State

- Active maintenance branch: `refactor/engineering-cleanup`, created from `feature/transcription-reference-tooling` at `291637e966ed08fca1d1f394012b1e64c42fb590` and published with upstream tracking at `origin/refactor/engineering-cleanup`.
- The cleanup and follow-up hardening preserve the transcription, memory, persistence, API, WebSocket, and desktop boundaries. No cloud services, models, UI features, or product redesign were added.
- The latest hardening work enforces HTTP(S)-only local LLM endpoint boundaries, contains portable conversation identifiers and generated WAV paths, waits for threaded audio owners on cancellation, rejects incomplete live finalization, preserves dirty annotation edits, and only ranks complete comparable experiment matrices.
- Repository organization is responsibility- and lifecycle-based: root scripts are split into `launch`, `benchmarks`, `datasets`, `validation`, `setup`, and `packaging`; generated reports are dated under `docs/reports/`; handoffs and superseded plans are dated under `docs/archive/handovers/`.
- The tracked root now contains only `.gitignore`, `AGENTS.md`, `CollectiveMindGraph.spec`, `README.md`, and `pyproject.toml`. The former root `agy.md` is archived as a dated handoff.
- Default pytest discovery includes both `tests/` and `realtime_backend/tests/`.
- Generated/local state is ignored, including `.venv-win/`, model and dataset contents, recordings, logs, backend data/temp directories, local databases, and `transcription_settings.json`; only `models/README.md` and `datasets/README.md` are tracked policy files.
- `transcription_settings.json` and the seeded demo transcript remain available locally but are no longer tracked.

## Architecture

- Desktop ownership: `src/collective_mindgraph_desktop/` handles UI, recording, backend transport, desktop persistence, and response parsing.
- Backend ownership: `realtime_backend/app/` handles configuration, preprocessing, VAD, ASR, selective retranscription, transcript formatting, streaming, HTTP APIs, and backend persistence.
- Evaluation ownership: `realtime_backend/app/evaluation/transcription_metrics.py` is authoritative for reference-based WER/CER/edit-distance evaluation.
- Glossary ownership: `realtime_backend/app/pipeline/transcription_glossary.py` owns glossary-file loading and resolution.
- Audio executable ownership: `realtime_backend/app/utils/audio_process.py` owns FFmpeg resolution.
- Runtime diagnostics are exposed through an immutable transcription runtime snapshot; callers must not reach into pipeline/provider private fields.
- File and WebSocket transcript payloads are built by `realtime_backend/app/pipeline/transcript_formatter.py`.
- Repository layout and lifecycle ownership: `docs/dev/REPOSITORY_STRUCTURE.md`; documentation lifecycle: `docs/README.md`; script inventory: `scripts/README.md`.
- Reusable annotation implementation remains in `tools/transcript_annotation/`; thin annotation, experiment, and export entry points live in their owned `scripts/` categories.
- Backend-local operational helpers remain in `realtime_backend/scripts/`, backend tests remain in `realtime_backend/tests/`, and cross-layer/root tests remain in `tests/`; these were not moved for aesthetics.

## Verified Behavior

- Hardening baseline at `115b133`: focused transcription suite `74 passed, 2 skipped, 2 warnings`; annotation/evaluation suite `43 passed`; unified offscreen suite `367 passed, 5 skipped, 5 warnings`.
- Hardening result: focused transcription suite `78 passed, 2 skipped, 2 warnings`; annotation/evaluation suite `49 passed`; unified offscreen suite `407 passed, 5 skipped, 5 warnings` in `139.44s` on Python `3.13.14`.
- Repository-organization result: transcription selection `70 passed, 2 skipped, 2 warnings`; annotation/evaluation `47 passed`; API/WebSocket `44 passed, 3 warnings`; desktop `90 passed`; memory `67 passed, 2 skipped, 3 warnings`; unified offscreen suite `407 passed, 5 skipped, 5 warnings` in `61.62s`.
- Optional skips are two unavailable local-LLM paths, one unconfigured real embedding model, one missing generic Turkish fixture, and one missing project meeting fixture.
- Remaining warnings are one Starlette TestClient deprecation and four `torch.jit.load` deprecations.
- A cached Faster-Whisper `small` CPU/int8 smoke on `cv_tr_000.wav` returned `ASR_STATUS=OK`, provider `faster_whisper`, the expected Turkish sentence, and no mock or GPU fallback.
- Source compilation, representative imports, and transcription/annotation/export/benchmark CLI help checks pass when the repository's documented `PYTHONPATH=src;.` environment is used.
- Eleven safe benchmark, dataset, validation, and annotation CLI `--help` checks pass from outside the repository; Bash and PowerShell syntax checks, launcher root resolution, PyInstaller entry paths, pytest discovery paths, ignore policy, and all tracked relative Markdown links pass.
- No active tracked document or command points at the former flat script paths or former maintained-document report locations. One historical branch-state path remains inside an archived handoff as dated evidence, not as an active link.
- The full suite no longer modifies tracked simulation reports.

## Durable Decisions

- Do not silently change transcription profiles, model/device defaults, VAD/preprocessing thresholds, selective retranscription defaults, fallback behavior, or persisted schemas.
- Keep raw, selected, and cleaned transcript data distinct; keep reference metrics distinct from heuristic confidence.
- Keep ASR provider, preprocessing, orchestration, evaluation, persistence, API, and desktop boundaries even when similar models exist across layers.
- Treat only HTTP(S) endpoints on exact localhost names or local/private IP addresses as local LLM endpoints; hostname prefixes and remote-access overrides are not URL-scheme validation.
- External conversation IDs must be validated at the route and service boundaries, fit the conservative Windows UTF-16 filename budget, and resolve to direct children of the configured store.
- Cancellation of a threaded audio stage must wait until its worker releases owned WAV files before cleanup; delayed cancellation is preferable to a Windows temp-file leak.
- A live transcription session is successful only after a final event; receiving partial text before disconnect is not completion.
- Dirty annotation edits must be flushed before segment, recording, dataset, or window-close navigation, and failed validation must keep the edit dirty.
- Transcription experiments may rank configurations or condition deltas only when the exact planned configuration-by-recording matrix is complete, failure-free, and has identical reference coverage; resume output is filtered to exact full-configuration experiment IDs.
- Do not commit real meeting audio, personal device identifiers, model weights, local databases, generated exports, or machine-specific paths.
- Preserve benchmark evidence and dated reports that support project claims.
- Do not move or delete user-local datasets, models, recordings, databases, or runtime directories automatically. Runtime persistence paths were intentionally preserved during organization.
- Use `scripts/` purpose directories for thin operational entry points, `tools/` for reusable developer applications/libraries, `docs/reports/YYYY-MM-DD/` for curated evidence, and `docs/archive/` for superseded material.
- Do not add compatibility wrappers for the former flat script paths unless an external consumer is identified; all tracked internal callers use the new paths.

## Deferred Risks

- Experiment resume fingerprints do not yet include reference text, glossary contents, audio content, or code version, so stale results can be reused after inputs change.
- Project benchmark reference discovery can ingest subtitle timing syntax or choose an unintended broad-glob match; benchmark entry points should also reject empty references and mock ASR explicitly.
- Some corpus reports macro-average per-recording WER/CER instead of aggregating edit counts, and long-reference Levenshtein evaluation uses quadratic memory.
- Dataset export names can collide after sanitization and exports can retain stale/excluded audio; use collision-resistant names and staged atomic replacement.
- Desktop persistence drops confirmed word timestamps. Uploads are read fully into memory, streaming backlog controls need stronger bounds, and desktop streaming/file parsing remains duplicated.
- Packaging omits some backend runtime assets/dependencies, desktop autostart accepts unsupported URL shapes, and embedding configuration uses inconsistent singular/plural names.
- Equivalent memory/provider modules exist in desktop/core and backend trees, but source-mode isolation and persistence ownership make consolidation risky without a dedicated migration plan.
- `llm_provider="disabled"` is inconsistent with the LLM builder's unknown-value fallback to LM Studio. Preserve current behavior until configuration semantics are explicitly migrated and tested.
- Environment/config naming remains partly duplicated across legacy `CMG_*` and `CMG_RT_*` aliases; external compatibility prevents silent removal.
- The console-script `pytest` entry point needs `PYTHONPATH=src;.` in this environment; without it, two root tests cannot import `realtime_backend` during collection.
- Real meeting-room Turkish WER/CER, Silero behavior on the target Windows runtime, packaging, and installer validation remain open validation work.

## Next Likely Tasks

- Gather human-reviewed, representative Turkish meeting audio before tuning ASR or reporting accuracy.
- Strengthen benchmark and experiment provenance: content/code fingerprints, strict reference parsing, mock-ASR rejection, and micro-aggregated edit counts.
- Make dataset export collision-safe and atomic before using it for larger annotation corpora.
- Preserve word timestamps end-to-end and bound upload/stream memory usage without changing the persisted schema silently.
- Resolve the LLM disabled/default contradiction through an explicit compatibility plan.
- Validate packaging and launch flows on the target tester machine.
- Treat any further memory-layer consolidation as a separate persistence-aware project.
