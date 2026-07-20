# Project Turkish Transcription Benchmark

Date: 2026-06-22

Status: `BENCHMARK_NOT_RUN_NO_AUDIO`

Scope: real Turkish transcription benchmarking only. This report does not evaluate graph persistence, Ask Memory, extraction, review workflow, UI, LLM reasoning, semantic retrieval, export/import, or diarization.

## Executive Summary

The project now has a local benchmark runner for real Turkish audio:

```text
scripts/benchmarks/run_project_turkish_transcription_benchmark.py
```

The benchmark has not been run because no project Turkish meeting-room audio file was available in the expected fixture location and no `--audio` path was provided. No accuracy, meeting-room readiness, or model superiority claim should be made from this report.

Current provisional default remains:

```text
model=large-v3
quality_profile=max_quality
language=tr
transcript_cleanup_mode=conservative
faster_whisper_internal_vad=false
external_vad_provider=silero when available
```

This recommendation is provisional until measured against a real Turkish meeting-room fixture with a human reference transcript.

## Existing Benchmark Assets Checked

Requested report file:

- `docs/reports/2026-06-30/transcription-benchmarks/PROJECT_TURKISH_TRANSCRIPTION_BENCHMARK.md`: created by this pass.

Requested scripts:

- `scripts/benchmarks/run_project_turkish_transcription_benchmark.py`: created by this pass.
- `scripts/benchmark_transcription_quality.py`: not found.

Existing related scripts:

- `realtime_backend/scripts/benchmark_common_voice_tr.py`: existing Common Voice Turkish benchmark helper. Useful for clean scripted speech regression, not a project meeting-room benchmark.
- `realtime_backend/scripts/check_transcription_test_readiness.py`: existing readiness checker.
- `realtime_backend/scripts/import_common_voice_tr_sample.py`: existing Common Voice importer.
- `realtime_backend/scripts/prepare_turkish_audio_fixture.py`: existing helper for the older `turkish_meeting_sample.wav` fixture path.

Existing fixtures:

- `realtime_backend/tests/fixtures/audio/common_voice_tr/*.wav`: present. These are Common Voice clean/test speech samples, not real project meeting-room audio.
- `realtime_backend/tests/fixtures/expected/common_voice_tr_manifest.json`: present.
- `realtime_backend/tests/fixtures/audio/turkish_meeting_sample.wav`: not found during this pass.
- `realtime_backend/tests/fixtures/audio/project_turkish/`: created with `.gitkeep`.
- `realtime_backend/tests/fixtures/expected/project_turkish/`: created with `.gitkeep`.

## Required Audio And Reference Files

To run the benchmark, add a local audio file such as:

```text
realtime_backend/tests/fixtures/audio/project_turkish/real_meeting_room_001.wav
```

Recommended matching human reference transcript:

```text
realtime_backend/tests/fixtures/expected/project_turkish/real_meeting_room_001.reference.txt
```

Minimum acceptable benchmark fixture:

- Local WAV, FLAC, MP3, M4A, or other ffmpeg-readable audio.
- Prefer WAV for inspectability.
- Turkish speech.
- Local recording only.
- No cloud transcription used to create the reference.
- Human-written reference transcript if WER/CER is desired.

## How To Run

With real meeting-room audio and a reference transcript:

```powershell
python scripts/benchmarks/run_project_turkish_transcription_benchmark.py `
  --audio realtime_backend/tests/fixtures/audio/project_turkish/real_meeting_room_001.wav `
  --reference realtime_backend/tests/fixtures/expected/project_turkish/real_meeting_room_001.reference.txt `
  --audio-kind real_meeting_room `
  --output docs/reports/2026-06-30/transcription-benchmarks/PROJECT_TURKISH_TRANSCRIPTION_BENCHMARK.md
```

Without a reference transcript:

```powershell
python scripts/benchmarks/run_project_turkish_transcription_benchmark.py `
  --audio realtime_backend/tests/fixtures/audio/project_turkish/real_meeting_room_001.wav `
  --audio-kind real_meeting_room `
  --output docs/reports/2026-06-30/transcription-benchmarks/PROJECT_TURKISH_TRANSCRIPTION_BENCHMARK.md
```

The no-reference run is useful for inspecting raw/cleaned transcripts and metadata, but it cannot support accuracy claims.

## Supported Benchmark Matrix

The runner defaults to:

| Model | Profile | Status |
|---|---|---|
| `large-v3` | `max_quality` | Supported; not run yet |
| `large-v3` | `balanced` | Supported; not run yet |
| `large-v3-turbo` | `max_quality` | Supported; not run yet |
| `large-v3-turbo` | `balanced` | Supported; not run yet |

Benchmark controls:

- `language=tr`
- `transcript_cleanup_mode=conservative`
- `CMG_RT_ASR_INTERNAL_VAD=false`
- `CMG_RT_ASR_WORD_TIMESTAMPS=true`
- `CMG_RT_ASR_CONDITION_ON_PREVIOUS_TEXT=false`
- external VAD requested as `silero`
- LLM correction disabled with `llm_provider=none`
- diarization disabled for text-quality isolation
- cloud access/download environment variables forced off by the runner
- `ASR_STATUS=MOCK_FALLBACK` invalidates the benchmark

## Report Fields Produced By Runner

When run, the report includes:

- date
- audio file path
- audio duration
- audio type: real meeting-room audio, test speech, noisy room, overlap sample, or unknown
- whether a human reference transcript exists
- model/profile tested
- ASR status
- mock fallback used or not
- preprocessing status
- VAD provider
- beam size
- compute type
- processing time
- raw transcript
- cleaned transcript
- WER and CER if a reference exists
- notable substitutions/deletions/insertions if a reference exists
- Turkish character preservation check for `Ã§`, `ÄŸ`, `Ä±`, `Ä°`, `Ã¶`, `ÅŸ`, `Ã¼`
- technical term preservation check for `Collective MindGraph`, `FastAPI`, `SQLite`, `PySide6`, `VAD`, `transcript`, `aksiyon`, `karar`
- heuristic VAD clipping notes
- final recommended default configuration
- unresolved issues

## Benchmark Results

No benchmark result exists yet.

Reason:

- No project Turkish meeting-room audio fixture was found.
- No `--audio` path was supplied in this task.

The Common Voice files present in `realtime_backend/tests/fixtures/audio/common_voice_tr/` were not used because they are clean/test speech and would not prove real meeting-room readiness.

## Accuracy Claims

No accuracy percentage is claimed.

No WER/CER is reported.

No model/profile is declared superior.

No real meeting-room readiness is claimed.

## Turkish Character Preservation

Not evaluated because benchmark did not run.

Required check when audio is available:

| Character | Raw Present | Cleaned Present |
|---|---|---|
| Ã§ | Not run | Not run |
| ÄŸ | Not run | Not run |
| Ä± | Not run | Not run |
| Ä° | Not run | Not run |
| Ã¶ | Not run | Not run |
| ÅŸ | Not run | Not run |
| Ã¼ | Not run | Not run |

## Technical Term Preservation

Not evaluated because benchmark did not run.

Required check when audio is available:

| Term | Raw Present | Cleaned Present |
|---|---|---|
| Collective MindGraph | Not run | Not run |
| FastAPI | Not run | Not run |
| SQLite | Not run | Not run |
| PySide6 | Not run | Not run |
| VAD | Not run | Not run |
| transcript | Not run | Not run |
| aksiyon | Not run | Not run |
| karar | Not run | Not run |

## VAD Clipping Notes

Not evaluated because benchmark did not run.

When run, the benchmark writes simple VAD boundary notes, but those notes are only heuristics. Manual listening review is still required to confirm whether soft Turkish word starts or endings were clipped.

## Verification

Commands run:

```text
python -m py_compile scripts/benchmarks/run_project_turkish_transcription_benchmark.py
python scripts/benchmarks/run_project_turkish_transcription_benchmark.py --help
```

Result:

- `py_compile` passed.
- CLI help printed successfully.

Targeted pytest:

```text
python -m pytest realtime_backend/tests/test_project_turkish_meeting_asr_quality.py realtime_backend/tests/test_common_voice_tr_asr_quality.py
```

Result:

- pytest not run: `No module named pytest`.

Actual benchmark run:

- No. No project Turkish audio file was available.

## Final Recommended Default Configuration

Current recommendation remains provisional:

```text
CMG_RT_ASR_PROVIDER=faster_whisper
CMG_RT_ASR_MODEL=large-v3
CMG_RT_LANGUAGE=tr
CMG_RT_TRANSCRIPTION_QUALITY_MODE=max_quality
CMG_RT_ASR_BEAM_SIZE=5
CMG_RT_ASR_MAX_QUALITY_BEAM_SIZE=8
CMG_RT_ASR_WORD_TIMESTAMPS=true
CMG_RT_ASR_INTERNAL_VAD=false
CMG_RT_ASR_CONDITION_ON_PREVIOUS_TEXT=false
CMG_RT_TRANSCRIPT_CLEANUP_MODE=conservative
CMG_RT_VAD_PROVIDER=silero
CMG_RT_LLM_PROVIDER=none
```

Rationale:

- It is the current local-first quality posture.
- It avoids mock fallback by recommending explicit `faster_whisper`.
- It forces Turkish.
- It preserves raw ASR and uses conservative cleanup.
- It keeps Faster-Whisper internal VAD disabled so external VAD remains visible/configurable.

Limit:

- This is not proven better than `large-v3-turbo + max_quality` or either balanced profile until a real local benchmark is run.

## Unresolved Issues

- Need real Turkish meeting-room audio.
- Need a human reference transcript for WER/CER.
- Need to run all four model/profile combinations locally.
- Need to confirm no `ASR_STATUS=MOCK_FALLBACK`.
- Need to inspect VAD clipping by listening.
- Need to compare raw transcript and conservative cleaned transcript separately.
- Need to keep Common Voice results separate from real meeting-room readiness claims.
