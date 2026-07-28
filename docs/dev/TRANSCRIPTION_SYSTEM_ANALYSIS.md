# Transcription System Analysis

## Ownership

- Use-case boundary:
  `src/collective_mindgraph/application/transcription/transcribe_recording.py`
- Processing port:
  `src/collective_mindgraph/application/transcription/processing_port.py`
- Concrete orchestration:
  `src/collective_mindgraph/infrastructure/transcription/recording_processor.py`
- ASR and profile resolution:
  `src/collective_mindgraph/infrastructure/transcription/asr.py`
- VAD:
  `src/collective_mindgraph/infrastructure/transcription/vad.py`
- Audio/FFmpeg:
  `src/collective_mindgraph/infrastructure/audio/`
- Transcript formatting:
  `src/collective_mindgraph/application/transcription/transcript_formatter.py`
- Reference metrics:
  `src/collective_mindgraph/application/transcription/evaluation/transcription_metrics.py`

## Data guarantees

The processing contract keeps raw ASR text, selected/cleaned text, word timing,
confidence diagnostics, and user corrections distinct. Corrections never
replace raw text. Transcript changes mark related insights and knowledge items
for renewed review.

## Provider boundary

Faster-Whisper, VAD, optional speaker separation, and local-model postprocessing
are infrastructure adapters. Importing the package does not load them. Settings
are composed inside engine lifespan.

## Quality boundary

Reference WER/CER is calculated only when a human reference transcript is
available. Heuristic confidence, audio-quality scores, and keyword overlap are
diagnostics and are not accuracy claims.

The repository includes clean Common Voice fixtures and optional project
meeting fixtures under `tests/transcription/fixtures/`. Clean scripted speech
does not validate noisy, overlapping, or far-field meeting-room behavior.

The pre-rework detailed analysis is retained at
`docs/archive/pre-rework/TRANSCRIPTION_SYSTEM_ANALYSIS.md`.
