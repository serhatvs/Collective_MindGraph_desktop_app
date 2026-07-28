# Reports

This folder is the archive for generated project reports and validation outputs. It keeps benchmark reports, simulation outputs, and validation checkpoints out of the project root and out of `docs/dev`, which is reserved for active developer documentation.

Reports are organized by run or checkpoint date:

- `2026-06-30/gpu-asr/`: GPU ASR routing, CPU/GPU runtime, ASR accuracy, VAD validation, and real-room validation planning.
- `2026-06-30/transcription-benchmarks/`: MediaSpeech TR and project Turkish transcription benchmark reports.
- `2026-06-30/simulation/`: Full-scale simulation reports, history, and exported simulation JSON.
- `2026-06-30/validation/`: Reserved for standalone validation summaries that are not specific to one benchmark family.
- `2026-07-03/validation/`: Integration-test hardening checkpoint.
- `2026-07-06/validation/`: Realistic transcript-fixture validation checkpoint.
- `2026-07-09/transcription-benchmarks/`: Transcription Quality V2 benchmark placeholder/output.
- `2026-07-19/transcription-benchmarks/`: Selective-retranscription benchmark placeholder/output.
- `archive/`: Older report outputs retained for traceability.

## Latest Validated Checkpoint

The latest dated report artifact is the `2026-07-19` selective-retranscription placeholder. It records that no new bad-microphone audio and human reference were supplied, so it makes no WER, CER, or improvement claim. The `2026-06-30` checkpoint remains the latest real GPU-routing and MediaSpeech benchmark group. None of these reports validates production meeting-room readiness or diarization.
