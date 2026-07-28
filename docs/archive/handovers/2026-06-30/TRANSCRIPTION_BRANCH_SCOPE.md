# Transcription Branch Scope

## Branch

`feature/transcription-quality-pipeline`

## Purpose

Isolate Turkish transcription maintenance from Collective MindGraph memory-product development. This branch is for preserving the current Turkish transcription baseline, validating safe claims, and fixing real transcription bugs only.

## Allowed Work

- ASR/STT bugfixes when a real transcript generation bug is found.
- Faster-Whisper configuration fixes only when the current baseline is broken or misleading.
- Turkish language defaults and language forcing fixes.
- Turkish character preservation fixes.
- Raw transcript and cleaned transcript separation fixes.
- Conservative transcript cleanup bugfixes.
- Audio preprocessing only if a real transcription bug requires it.
- VAD fixes only when they directly address a real transcription bug.
- Transcription benchmark scripts, fixtures, reports, and setup documentation.
- Safe-claim validation and local-first transcription setup documentation.

## Forbidden Work

- Graph memory system changes.
- Ask Memory changes.
- Human review lifecycle changes.
- Export/import changes.
- Job system changes unless limited to transcription job execution or diagnostics.
- UI redesign or non-transcription UI polish.
- Diarization implementation or claims.
- Speaker separation implementation or claims.
- Hardware/device work unrelated to ASR runtime validation.
- Patent, marketing, or product-claim documentation unrelated to transcription quality.

## Memory Track Boundary

The memory track is the main product development track. This transcription branch must not touch graph memory, Ask Memory, review lifecycle, graph reasoning, or memory UI work.

## Current Baseline Assumptions

- Local ASR uses Faster-Whisper.
- Default Turkish transcription settings are currently oriented around `language=tr`, conservative cleanup, and explicit mock fallback reporting.
- GPU-routed local ASR has been validated through the real backend transcription path, but this does not prove meeting-room readiness.
- MediaSpeech TR benchmark results are useful for clean Turkish media speech only.
- Real Turkish meeting-room audio remains a required separate benchmark.
- Silero VAD is not yet validated in the current Windows environment.
- Diarization is not implemented and is roadmap only.
- Speaker separation is not implemented and is roadmap only.

## Claim Boundary

Do not claim transcription accuracy without benchmark evidence from a human reference transcript. Do not claim meeting-room readiness until real meeting-room Turkish audio has been tested. Treat `ASR_STATUS=MOCK_FALLBACK` as invalid benchmark output.
