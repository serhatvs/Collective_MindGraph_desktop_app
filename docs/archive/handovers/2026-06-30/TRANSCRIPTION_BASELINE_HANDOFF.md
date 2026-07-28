# Transcription Baseline Handoff

Date: 2026-06-30

Purpose: freeze the current transcription state and hand the project from transcription work to transcript-to-memory work. This document is a baseline note, not a new ASR tuning plan.

## Current Git State

- Current branch: `feature/transcription-quality-pipeline`
- Branch relation: up to date with `origin/feature/transcription-quality-pipeline`
- Current HEAD: `5824ef5 ...`
- Latest relevant transcription checkpoint tag in history: `gpu-asr-diagnostics-benchmarks-validated` at commit `d80b97d`
- Tags directly on HEAD: none found
- Working tree at handoff time: not clean before this document was added
  - Modified: `docs/dev/codex.md`
  - Untracked: `docs/dev/TRANSCRIPTION_BRANCH_SCOPE.md`

## Current Transcription Baseline

The current transcription baseline is the local-first Faster-Whisper transcription pipeline as documented by:

- `docs/dev/TRANSCRIPTION_QUALITY_CHECKPOINT.md`
- `docs/dev/TRANSCRIPTION_SYSTEM_ANALYSIS.md`
- `docs/reports/2026-06-30/transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK.md`
- `docs/reports/2026-06-30/gpu-asr/FULL_SCALE_GPU_ASR_TEST_REPORT.md`
- `docs/reports/2026-06-30/gpu-asr/CPU_VS_GPU_ASR_BENCHMARK_REPORT.md`
- `docs/reports/2026-06-30/gpu-asr/SILERO_VAD_ASR_VALIDATION_REPORT.md`
- `docs/reports/2026-06-30/gpu-asr/ASR_ACCURACY_BENCHMARK_REPORT.md`
- `docs/reports/2026-06-30/gpu-asr/REAL_ROOM_AUDIO_VALIDATION_PLAN.md`

Baseline behavior:

- Speech-to-text is local-first and cloud STT is not part of the baseline.
- Faster-Whisper is the real ASR path when available.
- Mock fallback is no longer silent; it is exposed as `ASR_STATUS=MOCK_FALLBACK`, `mock_fallback_used=true`, and warning metadata.
- Turkish is forced by default through `language=tr`.
- Raw ASR text is preserved separately from cleaned text.
- Conservative transcript cleanup is the default.
- ASR quality profiles are explicit: `fast`, `balanced`, and `max_quality`.
- Faster-Whisper internal VAD is disabled by default; external VAD/chunking controls segmentation.
- The backend exposes diagnostic metadata for ASR model, device, compute type, language, profile, VAD provider, GPU routing, fallback state, and preprocessing status.
- GPU-routed ASR through the real CMG backend path has been validated locally with Faster-Whisper/CUDA on a Turkish WAV.
- Clean MediaSpeech TR benchmark results exist and show `large-v3-turbo` as the practical clean-media-speech winner, especially with `balanced`, but that does not establish meeting-room readiness.

## Frozen Scope

The following transcription/audio areas are frozen for the next phase and must not be changed without a new, specific bug or a deliberate reopened ASR milestone:

- Audio preprocessing behavior
- ffmpeg normalization behavior
- VAD provider selection, thresholds, padding, region splitting, and fallback behavior
- Faster-Whisper model loading, decoding, device, compute, language, and word timestamp settings
- ASR runtime profile resolution
- Transcription quality profiles
- Turkish cleanup behavior
- Benchmark scripts, benchmark interpretation, and benchmark pass/fail boundaries
- Diarization and speaker separation assumptions
- Mock fallback signaling
- GPU ASR diagnostic behavior

This freeze does not mean transcription is perfect. It means transcription has reached a documented checkpoint that is good enough to unblock memory-pipeline work.

## Must Not Be Touched Without New Reason

Do not continue improving or tuning:

- audio preprocessing
- ffmpeg normalization
- VAD settings
- Faster-Whisper settings
- transcription quality profiles
- benchmark logic
- diarization
- speaker separation

Acceptable reasons to reopen transcription work:

- A clear bug prevents generating a transcript for memory extraction.
- A regression makes `ASR_STATUS` or fallback metadata misleading.
- A memory-pipeline integration exposes missing transcript fields that can only be fixed at the transcription contract boundary.
- The user explicitly starts a new transcription/ASR milestone.

## Known Limitations

- Real Turkish meeting-room audio has not been validated.
- Clean MediaSpeech TR benchmark results are not proof of noisy, far-field, multi-speaker meeting performance.
- Silero VAD did not load in one Windows validation path and ASR continued with EnergyVAD fallback.
- Diarization and true speaker separation are not implemented or validated.
- WER/CER accuracy was not computed for the GPU routing checkpoint because no reference transcript was supplied for that run.
- Conservative cleanup still changes punctuation, casing, spacing, and may append final punctuation.
- `ASR_STATUS=MOCK_FALLBACK` remains possible when `auto` provider cannot load Faster-Whisper; consumers must fail closed on it.

## Safe Claims

Safe to claim:

- Collective MindGraph has a local-first transcription pipeline.
- The real ASR path uses Faster-Whisper when it loads successfully.
- Mock fallback is explicitly surfaced and should not be mistaken for real transcription.
- Turkish transcription can be forced with `language=tr`.
- Raw and cleaned transcript text are represented separately.
- GPU-routed Faster-Whisper ASR was validated through the real backend path on local Turkish audio.
- Clean MediaSpeech TR benchmark evidence exists for a limited clean-media-speech subset.
- The current baseline is sufficient to begin transcript-to-memory extraction work.

## Unsafe Claims

Do not claim:

- Production-ready Turkish meeting transcription.
- Validated real meeting-room readiness.
- Validated diarization or speaker separation.
- Universally best ASR model/profile for all Turkish audio.
- Guaranteed transcription accuracy for noisy, overlapping, distant-microphone, or multi-speaker meetings.
- That `large-v3-turbo` or `large-v3` is the final project-wide default for all use cases.
- That transcription quality should continue to be tuned before memory work can begin.

## Next Recommended Milestone

Move to:

`Transcript -> Structured Memory Pipeline`

Recommended branch name:

`feature/transcript-to-memory-pipeline`

Focus areas:

- Extract structured items from existing transcript text.
- Detect tasks, decisions, topics, risks, and open questions.
- Preserve source references back to transcript spans, segment IDs, timestamps, and speaker labels when available.
- Add human review before committing extracted memory.
- Persist reviewed memory items into the memory graph.
- Build evidence-only Ask Memory behavior that answers from stored, cited memory rather than unsupported inference.

Initial implementation boundary:

- Start from transcript data already emitted by the current pipeline.
- Do not modify audio or ASR behavior.
- Do not begin by tuning graph algorithms.
- Define the transcript-to-memory contract first: input transcript shape, extracted item schema, evidence references, review states, and persistence handoff.

## Suggested Next Codex Prompt Topic

Suggested prompt:

```text
Implement the first Transcript -> Structured Memory Pipeline milestone. Do not modify transcription/audio code. Start from existing transcript outputs and design the extraction schema for tasks, decisions, topics, risks, and open questions with source references and human review states.
```

## Handoff Summary

Transcription is now treated as frozen at the documented baseline. The next useful project risk is no longer "can we make ASR a little better"; it is "can the app turn a transcript into auditable, reviewable, persistent memory without inventing unsupported facts."
