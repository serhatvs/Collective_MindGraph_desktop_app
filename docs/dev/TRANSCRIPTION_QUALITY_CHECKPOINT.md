# Transcription Quality Checkpoint

Date: 2026-06-22

Scope: first quality-hardening pass for speech-to-text only. This checkpoint intentionally excludes graph persistence, Ask Memory, extraction, review workflow, UI polish, LLM reasoning, and diarization.

## Executive Summary

The transcription subsystem now reports mock ASR fallback explicitly, exposes benchmark-ready metadata on every pipeline result, resolves explicit ASR quality profiles, defaults to conservative Turkish cleanup, and records basic preprocessing diagnostics. These changes improve demo safety and measurement readiness, but they do not prove transcription accuracy and do not validate real Turkish meeting-room performance.

Real Turkish meeting audio tested: No.

Benchmark run: No.

Reason: the local Windows Python environment does not have `pytest` installed, and no real Turkish meeting-room WAV fixture was available in the checkout during this pass.

## What Changed

### Mock ASR Fallback Is Explicit

Files:

- `realtime_backend/app/pipeline/asr.py`
- `realtime_backend/app/pipeline/orchestrator.py`
- `realtime_backend/app/api/routes.py`
- `realtime_backend/app/api/ws.py`
- `realtime_backend/app/models.py`

Changes:

- Added ASR status constants:
  - `ASR_STATUS=OK`
  - `ASR_STATUS=MOCK_EXPLICIT`
  - `ASR_STATUS=MOCK_FALLBACK`
- `CMG_RT_ASR_PROVIDER=auto` fallback now returns `MockASR(asr_status="ASR_STATUS=MOCK_FALLBACK")`.
- Mock ASR output now includes unmistakable placeholder text and `confidence=0.0`.
- Pipeline metadata includes `asr_status`, `ASR_STATUS`, `mock_fallback_used`, warnings, and optional fallback reason.
- `/health`, `/transcribe/file`, and WebSocket partial/final transcript events expose ASR status and warnings.

Quality impact:

- Prevents mock text from looking like real transcription.
- Makes local runtime/model load failures visible to API clients and diagnostics.

Remaining risk:

- Clients still need to treat `ASR_STATUS=MOCK_FALLBACK` as a failed quality state.

Confidence: High.

### Explicit ASR Quality Profiles

Files:

- `realtime_backend/app/config.py`
- `realtime_backend/app/pipeline/asr.py`
- `realtime_backend/app/pipeline/orchestrator.py`

Profiles:

| Profile | Beam Size | Word Timestamps | Faster-Whisper Internal VAD | Condition On Previous Text | Notes |
|---|---:|---|---|---|---|
| `fast` | `1` | enabled by default | disabled by default | disabled by default | Lowest-latency profile. |
| `balanced` | `max(3, CMG_RT_ASR_BEAM_SIZE)` | enabled by default | disabled by default | disabled by default | Middle profile for comparison. |
| `max_quality` | `max(5, CMG_RT_ASR_MAX_QUALITY_BEAM_SIZE, CMG_RT_ASR_BEAM_SIZE)` | enabled by default | disabled by default | disabled by default | Default profile; beam defaults to `8`. |

Defaults after this pass:

```text
CMG_RT_ASR_MODEL=large-v3
CMG_RT_TRANSCRIPTION_QUALITY_MODE=max_quality
CMG_RT_ASR_BEAM_SIZE=5
CMG_RT_ASR_MAX_QUALITY_BEAM_SIZE=8
CMG_RT_LANGUAGE=tr
CMG_RT_ASR_WORD_TIMESTAMPS=true
CMG_RT_ASR_INTERNAL_VAD=false
CMG_RT_ASR_CONDITION_ON_PREVIOUS_TEXT=false
```

Compatibility:

- Legacy `quality_mode=accurate` maps to `max_quality`.

Quality impact:

- Makes decode behavior measurable and visible.
- Keeps external VAD as the default segmentation control.

Remaining risk:

- No benchmark has proven that `large-v3` plus `max_quality` beats `large-v3-turbo` or `balanced` for this project’s Turkish meeting use case.

Confidence: High for code behavior; Medium for quality benefit until benchmarked.

### Turkish Cleanup Is Safer

Files:

- `realtime_backend/app/config.py`
- `realtime_backend/app/utils/turkish_cleanup.py`
- `realtime_backend/app/pipeline/orchestrator.py`

Changes:

- Added `CMG_RT_TRANSCRIPT_CLEANUP_MODE`.
- Default cleanup mode is `conservative`.
- Conservative mode does not remove filler words.
- Aggressive mode can remove common Turkish filler tokens.
- Raw ASR text remains preserved in `TranscriptSegment.raw_text`.
- Cleaned transcript remains separate in `TranscriptSegment.corrected_text`.

Quality impact:

- Reduces risk that discourse markers such as `şey`, `yani`, or `işte` are deleted from default cleaned transcripts.
- Keeps raw ASR available for evaluation.

Remaining risk:

- Conservative cleanup still changes capitalization, spacing, repeated punctuation, and may append final punctuation.
- Python casing is not Turkish-locale-aware for dotted/dotless `i`.

Confidence: High.

### Preprocessing Diagnostics Improved

Files:

- `realtime_backend/app/utils/audio_process.py`
- `realtime_backend/app/pipeline/orchestrator.py`
- `realtime_backend/app/models.py`

Changes:

- Added `inspect_audio`.
- Pipeline now records:
  - `preprocessing_status`
  - `ffmpeg_normalization_succeeded`
  - input WAV sample rate, channels, duration, format when inspectable
  - ASR-input WAV sample rate, channels, duration, format when inspectable
  - warning metadata when ffmpeg fails and original file is used

Quality impact:

- Makes it easier to compare benchmark runs and diagnose format problems.

Remaining risk:

- Inspection currently uses Python `wave`, so non-WAV source metadata is usually unavailable before ffmpeg conversion.
- RMS, loudness, clipping, denoise, high-pass filtering, and gain diagnostics are still missing.

Confidence: High.

### Benchmark-Ready Metadata Added

Files:

- `realtime_backend/app/pipeline/orchestrator.py`
- `realtime_backend/app/models.py`
- `realtime_backend/app/pipeline/transcript_formatter.py`
- `realtime_backend/app/api/routes.py`
- `realtime_backend/app/api/ws.py`

Every pipeline result now includes, when available:

- `asr_provider`
- `model_name`
- `quality_profile`
- `language`
- `beam_size`
- `compute_type`
- `vad_provider`
- `preprocessing_status`
- `processing_time_seconds`
- `mock_fallback_used`
- `asr_status`
- `warnings`
- `transcript_cleanup_mode`

Quality impact:

- Enables future ASR comparisons without relying on logs or environment memory.

Remaining risk:

- Metadata alone is not a benchmark. WER/CER or reference comparison must still be run on real fixtures.

Confidence: High.

## Remaining Quality Risks

Critical:

- Real Turkish meeting-room audio has not been validated.
- `large-v3` vs `large-v3-turbo` has not been compared on project audio after the default change.
- Clients must fail closed on `ASR_STATUS=MOCK_FALLBACK`.

High:

- CUDA/float16 defaults can fail on machines without the correct GPU/runtime.
- VAD padding and split settings are not tuned against soft Turkish word starts/endings.
- No objective benchmark was run in this pass.
- Cleanup still changes text in conservative mode through punctuation/casing.

Medium:

- `CMG_RT_ASR_MAX_QUALITY_BEAM_SIZE=8` may be too slow on some local hardware.
- `condition_on_previous_text=false` may reduce continuity across chunks, though it helps avoid cross-chunk hallucination.
- Preprocessing has no loudness, clipping, or noise diagnostics.

Low:

- Faster-Whisper engine choice is not yet proven to be a quality bottleneck.

## Recommended Next Test Audio

Use local-only audio fixtures with matching human reference transcripts:

1. Clean near-field Turkish speech, single speaker, 1-2 minutes.
2. Real Turkish meeting-room conversation, 2-4 speakers, 5-10 minutes.
3. Noisy room recording with HVAC or laptop microphone noise.
4. Overlapping Turkish speech sample, even if short.
5. Technical vocabulary sample containing `Collective MindGraph`, `FastAPI`, `SQLite`, `PySide6`, `VAD`, `transcript`, `aksiyon`, `karar`, and Turkish characters.
6. Quiet speaker sample with soft word starts and endings.

For each fixture, save:

- Original audio.
- Human reference transcript.
- Notes about microphone, room, distance, and speaker count.
- Pipeline metadata JSON.
- Raw transcript.
- Cleaned transcript.
- WER/CER or reviewed diff output.

## Validation Status

Ran:

```text
python -m py_compile realtime_backend/app/config.py realtime_backend/app/pipeline/asr.py realtime_backend/app/pipeline/orchestrator.py realtime_backend/app/utils/audio_process.py realtime_backend/app/utils/turkish_cleanup.py realtime_backend/app/models.py realtime_backend/app/api/routes.py realtime_backend/app/api/ws.py realtime_backend/app/pipeline/transcript_formatter.py realtime_backend/app/pipeline/vad.py
python -m py_compile realtime_backend/tests/test_asr.py realtime_backend/tests/test_transcript_quality.py realtime_backend/tests/test_api_routes.py realtime_backend/tests/test_transcript_formatter.py
```

Result:

- Python compilation passed for touched runtime files.
- Python compilation passed for touched test files.

Attempted:

```text
python -m pytest realtime_backend/tests/test_asr.py realtime_backend/tests/test_transcript_quality.py realtime_backend/tests/test_api_routes.py realtime_backend/tests/test_transcript_formatter.py
```

Result:

- Not run. The active Windows Python (`Python313`) reported: `No module named pytest`.

Benchmark run:

- No.

Real Turkish meeting audio tested:

- No.

## Recommended Next Actions

Immediate:

- Install/use a Python environment with `pytest` and run the targeted tests.
- Run `/health` in the actual demo environment and confirm no `ASR_STATUS=MOCK_FALLBACK`.
- Transcribe a short known Turkish WAV and inspect metadata for `model_name`, `quality_profile`, `beam_size`, `language`, `preprocessing_status`, and `mock_fallback_used=false`.

Next:

- Add the real Turkish meeting fixture and human reference transcript.
- Run `large-v3` vs `large-v3-turbo` with `balanced` and `max_quality`.
- Compare raw ASR and conservative cleaned output separately.
- Add loudness/clipping/RMS diagnostics.

Long-term:

- Build a repeatable local Turkish ASR benchmark suite.
- Add Turkish-aware WER/CER tooling.
- Evaluate preprocessing profiles with real noisy meeting audio.

## Bottom Line

This pass makes the transcription pipeline more honest and benchmark-ready. It does not establish accuracy, meeting-room readiness, or superiority of any model/profile. The next quality milestone is a real local Turkish benchmark with reference transcripts and no mock fallback.
