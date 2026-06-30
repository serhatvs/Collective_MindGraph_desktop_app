# Transcription Track Scope

## Current branch name

`feature/transcription-quality-pipeline`

## Purpose

Preserve, validate, benchmark, and safely bugfix Turkish transcription while keeping memory-product work isolated.

## Allowed work

- ASR / STT pipeline behavior
- Faster-Whisper settings
- Turkish language defaults
- Turkish character preservation
- raw_transcript / cleaned_transcript separation
- transcript cleanup
- transcription benchmark scripts
- transcription setup docs
- transcription bugfixes
- audio preprocessing only if a real transcription bug requires it

## Forbidden work

- memory graph
- Ask Memory
- human review lifecycle
- graph reasoning
- visual graph UI
- hardware/device code outside direct ASR runtime validation
- patent wording
- diarization
- speaker separation
- unrelated refactors

## Safe claims

- Local ASR uses Faster-Whisper when configured and available.
- Mock fallback is explicitly reported and is not valid benchmark output.
- GPU ASR routing has been validated through the CMG backend path.
- Clean Turkish MediaSpeech benchmark results exist for selected Faster-Whisper configurations.

## Unsafe claims

- Production diarization exists.
- Real speaker separation exists.
- Speaker_1 / Speaker_2 production attribution exists.
- Meeting-room Turkish transcription is validated.
- Accuracy claims are proven without a human reference benchmark.

## Reminder

Do not continue ASR or audio improvement unless a real bug is found or an explicit ASR milestone reopens that scope.
