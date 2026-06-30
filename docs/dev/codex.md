# codex.md

## Project
- Name: Collective MindGraph
- Type: Native Windows-first desktop application
- Stack: Python 3.11+, PySide6, SQLite
- Philosophy: Local-first, offline-capable, privacy-focused.

## Current State
- **Architecture**: Transitions to a strictly local-first design. All cloud AI providers (Amazon Bedrock, Deepgram) have been removed.
- **Desktop UI**: `src/collective_mindgraph_desktop` provides a `QMainWindow` with session explorer, voice command panel, and session detail view.
- **Legacy UI Compatibility**: `src/collective_mindgraph_desktop/ui/session_detail_panel.py` is restored as a compatibility aggregate panel for older product-loop tests while the main app keeps the newer page-based layout.
- **Backend**: `realtime_backend` FastAPI service handles transcription and LLM correction using local-only providers. Diarization is planned for future release.
- **Transcription**: Uses `faster-whisper` (local) for STT and `silero-vad` for voice activity detection.
- **Transcription Quality Hardening**: First STT hardening pass is implemented. `auto` fallback to `MockASR` now reports `ASR_STATUS=MOCK_FALLBACK`, mock output is unmistakable placeholder text with warning metadata, ASR quality profiles are explicit (`fast`, `balanced`, `max_quality`), `max_quality` is the default, Faster-Whisper internal VAD is off by default, and Turkish cleanup defaults to conservative mode without filler deletion.
- **Transcription Branch Scope**: Branch `feature/transcription-quality-pipeline` was created for isolated Turkish transcription quality work. Scope is documented in `docs/dev/TRANSCRIPTION_BRANCH_SCOPE.md`; do not use this branch for graph memory, Ask Memory, review workflow, export/import, UI redesign, diarization, or non-transcription claim work.
- **LLM Correction**: Defaults to `lmstudio` or other OpenAI-compatible local endpoints for transcript cleanup.
- **Extraction Fallback**: Local LLM extraction probes availability even when configured for heuristic fallback, reports reachable/unreachable status, and populates deterministic structured fallback items for full-scale graph simulations.
- **Diarization**: (Roadmap) Automatic speaker separation is not currently implemented or validated.
- **V2 Architecture**: A spreadsheet-driven V2 scaffold is under development in `src/collective_mindgraph` to formalize domain boundaries.
- **Packaging**: Supports single-file Windows builds via PyInstaller, bundling the local backend (using lighter fallbacks for VAD instead of the full `pyannote`/`torch` stack).
- **Validation**: Full local test suite currently passes with `PYTHONPATH=src:. realtime_backend/.venv/bin/python -m pytest` (`155 passed, 3 skipped`).
- **Current-State Report**: `docs/dev/CURRENT_STATE_ANALYSIS.md` was added as an honest checkpoint. It classifies the system as an advanced local-first MVP, not production-ready, and flags claim boundaries around diarization, speaker separation, semantic retrieval defaults, LLM stability, Ask Memory schema mismatch, duplicated graph/search services, packaging, and real meeting-room validation.
- **Transcription Audit**: `docs/dev/TRANSCRIPTION_SYSTEM_ANALYSIS.md` was added and updated after the first hardening pass. It maps the STT-only pipeline and now reflects explicit mock fallback status, `large-v3`/`max_quality` defaults, conservative cleanup, preprocessing diagnostics, and the need for real meeting-room Turkish validation before quality claims.
- **Transcription Checkpoint**: `docs/dev/TRANSCRIPTION_QUALITY_CHECKPOINT.md` records the first quality-hardening pass. No real Turkish meeting audio benchmark was run in the local Windows environment because `pytest` is unavailable and no real meeting fixture was present.
- **Transcription Freeze / Handoff**: `docs/dev/TRANSCRIPTION_BASELINE_HANDOFF.md` freezes the current transcription baseline on branch `feature/transcription-quality-pipeline` and redirects near-term work to `Transcript -> Structured Memory Pipeline`. Do not continue audio preprocessing, ffmpeg normalization, VAD, Faster-Whisper settings, quality profiles, benchmark logic, diarization, or speaker separation unless a clear new bug or explicit new ASR milestone is opened.
- **Project Turkish Benchmark Workflow**: `scripts/run_project_turkish_transcription_benchmark.py` was added to run local Faster-Whisper Turkish benchmarks across `large-v3`/`large-v3-turbo` and `max_quality`/`balanced`. `docs/reports/2026-06-30/transcription-benchmarks/PROJECT_TURKISH_TRANSCRIPTION_BENCHMARK.md` currently records `BENCHMARK_NOT_RUN_NO_AUDIO`; no real meeting-room audio fixture was present. `docs/dev/PROJECT_TURKISH_AUDIO_FIXTURE_GUIDE.md` explains how to record local fixtures.
- **MediaSpeech TR Local Benchmark**: `C:\Users\Serhat\Downloads\TR` was inspected as an external local Turkish MediaSpeech dataset. It contains `2,513` `.wav` files and `2,513` same-stem `.txt` references under `TR\`. `docs/dev/MEDIASPEECH_TR_LOCAL_MANIFEST.md` records the structure. `.venv-win` now exists with Python 3.13.13 because Python 3.11 was not installed, and benchmark/backend dependencies including `pydantic`, Faster-Whisper, and `pydantic-settings` were installed there. Blockers successfully resolved: `ffmpeg` is available via `CMG_RT_FFMPEG_PATH`, offline-caching works after a temporary online run, and the `[WinError 1314]` symlink issue for `large-v3-turbo` in `huggingface_hub` was patched. The 200-file subset successfully benchmarked using EnergyVAD to bypass `torch_python.dll` block across 2 configurations of `large-v3-turbo`. Interpretation: `large-v3-turbo` is the clear model winner for clean MediaSpeech TR, with `balanced` as the practical speed/quality winner (WER: 0.1527) and `max_quality` as the lowest-WER option (WER: 0.1526). Project-wide default remains provisional. Results stored in `docs/reports/2026-06-30/transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK.md`.
- **GPU ASR Validation**: `realtime_backend/app/pipeline/asr_runtime_config.py` now centralizes ASR runtime profile resolution for `CMG_RUNTIME_PROFILE`, `CMG_GPU_ENABLED`, `CMG_REQUIRE_GPU`, `CMG_ASR_*`, and existing `CMG_RT_*` aliases. The real backend path `TranscriptionPipeline -> FasterWhisperASR -> faster_whisper.WhisperModel` uses the resolved config and logs startup diagnostics distinguishing CUDA availability, GPU request, actual CUDA ASR load, and fallback. `scripts/check_asr_gpu.py` and `scripts/full_scale_gpu_transcription_test.py` were added. On 2026-06-30, small-model smoke loaded Faster-Whisper on CUDA and was observed by `nvidia-smi`; full-scale `large-v3`/`cuda`/`float16` transcribed a real local MediaSpeech TR WAV through the full CMG pipeline with `ASR_STATUS=OK`, no mock fallback, and GPU loaded. `nvidia-cublas-cu12`, `nvidia-cuda-runtime-cu12`, and `nvidia-cuda-nvrtc-cu12` were installed in `.venv-win`, and venv-local CUDA DLL directories are registered before Faster-Whisper loads. Report: `docs/reports/2026-06-30/gpu-asr/FULL_SCALE_GPU_ASR_TEST_REPORT.md`. This validates ASR GPU routing, not meeting-room readiness.
- **ASR Diagnostics & Benchmarks**: `/health`, desktop `BackendHealthStatus`, the voice status line, and the Diagnostics tab now expose ASR backend/model/device/compute/language, runtime profile, GPU enabled/required, CUDA availability, GPU requested, GPU actually used by ASR, fallback state/reason, embedding device, local LLM state, and VAD provider. New scripts: `scripts/benchmark_cpu_vs_gpu_asr.py`, `scripts/validate_silero_vad_asr.py`, and `scripts/benchmark_asr_accuracy.py`, backed by `scripts/asr_benchmark_common.py`. Reports created on 2026-06-30: `docs/reports/2026-06-30/gpu-asr/CPU_VS_GPU_ASR_BENCHMARK_REPORT.md` (small model CPU/GPU runtime comparison), `docs/reports/2026-06-30/gpu-asr/SILERO_VAD_ASR_VALIDATION_REPORT.md` (Silero requested but fell back to EnergyVAD; ASR continued), and `docs/reports/2026-06-30/gpu-asr/ASR_ACCURACY_BENCHMARK_REPORT.md` (runtime-only, WER/CER not computed because no reference was supplied). `docs/reports/2026-06-30/gpu-asr/REAL_ROOM_AUDIO_VALIDATION_PLAN.md` defines the future meeting-room validation plan.
- **Report Archive**: Generated benchmark, validation, and simulation outputs now live under `docs/reports/` with date-based folders. The latest checkpoint is `docs/reports/2026-06-30/`; `docs/dev/` should stay focused on active developer guides and technical documentation.
- **Agent Handoff**: `agy.md` (repo root) was created on 2026-06-22 by Antigravity as a durable working memory file for all future agent sessions. It captures dataset, blocker, environment, and exact next-step commands. Read it at the start of every benchmark-focused session.
- **Two-Track Setup**: A documentation-only split plan now separates `feature/transcription-quality-pipeline` for transcription maintenance/validation/bugfixes from planned `feature/transcript-to-memory-pipeline` work for transcript-to-structured-memory product development. Branch/worktree creation must wait for a clean working tree.

## Removed Features
- **Cloud STT**: Deepgram Nova-3 integration removed.
- **Cloud LLM**: Amazon Bedrock / Amazon Nova support removed.
- **External Dependencies**: `boto3`, `botocore`, and other cloud SDKs removed.

## Future Tasks
- [x] Install/find ffmpeg and verify `ffmpeg -version` (or set `CMG_RT_FFMPEG_PATH`).
- [x] Cache `large-v3` and `large-v3-turbo` with online mode (`HF_HUB_OFFLINE=0`).
- [x] Run benchmark with `EnergyVAD` + `CPU/int8` to get the first valid ASR results.
- [x] Update `docs/reports/2026-06-30/transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK.md` with actual WER/CER.
- [ ] Add real Turkish audio fixture test for Faster-Whisper language forcing.
- [ ] Run targeted transcription tests in an environment with `pytest`.
- [ ] Add real Turkish meeting-room WAV/reference fixtures under `realtime_backend/tests/fixtures/audio/project_turkish/` and `realtime_backend/tests/fixtures/expected/project_turkish/`.
- [x] Run `scripts/run_project_turkish_transcription_benchmark.py` and compare `large-v3` vs `large-v3-turbo` with `balanced` and `max_quality`.
- [x] Add and run CMG-path GPU ASR validation (`small` smoke and `large-v3` full pipeline) with `CMG_REQUIRE_GPU=1`.
- [x] Add CPU/GPU runtime, Silero VAD, and WER/CER benchmark scripts with reports.
- [ ] Validate Silero VAD itself in the current Windows environment; the first separate validation showed Silero did not load and ASR continued with EnergyVAD fallback.
- [ ] Run `scripts/benchmark_asr_accuracy.py` with a real reference transcript to compute WER/CER.
- [ ] Execute `docs/reports/2026-06-30/gpu-asr/REAL_ROOM_AUDIO_VALIDATION_PLAN.md` with real meeting-room Turkish audio fixtures and human references.
- [ ] Start `Transcript -> Structured Memory Pipeline`: extraction from transcripts, task/decision/topic/risk/open-question detection, source references, human review, memory graph persistence, and evidence-only Ask Memory.
- [ ] Create `feature/transcript-to-memory-pipeline` and the recommended `../cmg-memory` worktree once the current dirty working tree is resolved.
- [ ] Create or verify `../cmg-transcription` only after deciding whether the current repo should remain on `feature/transcription-quality-pipeline` or move elsewhere, because that branch is currently checked out in the original repo.
- [ ] Keep further transcription/audio improvements frozen unless a clear bug or explicit ASR milestone reopens that scope.
- [ ] Formalize V2 domain implementations following the spreadsheet-driven architecture.
- [ ] Defer diarization/speaker separation work until after transcript-to-memory progress or an explicit reopened audio milestone.
- [ ] Optimize onefile build size for full local model distribution.
