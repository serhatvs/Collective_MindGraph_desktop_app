# Reports

This folder is the archive for generated project reports and validation outputs. It keeps benchmark reports, simulation outputs, and validation checkpoints out of the project root and out of `docs/dev`, which is reserved for active developer documentation.

Reports are organized by run date:

- `2026-06-30/gpu-asr/`: GPU ASR routing, CPU/GPU runtime, ASR accuracy, VAD validation, and real-room validation planning.
- `2026-06-30/transcription-benchmarks/`: MediaSpeech TR and project Turkish transcription benchmark reports.
- `2026-06-30/simulation/`: Full-scale simulation reports, history, and exported simulation JSON.
- `2026-06-30/validation/`: Reserved for standalone validation summaries that are not specific to one benchmark family.
- `archive/`: Older report outputs retained for traceability.

## Latest Validated Checkpoint

The latest checkpoint is `2026-06-30`. It validates local GPU ASR routing through Faster-Whisper CUDA on a real Turkish WAV, documents MediaSpeech TR benchmark results, and preserves full-scale simulation outputs. The checkpoint does not validate production meeting-room readiness, diarization, or Silero VAD success in the current Windows environment.
