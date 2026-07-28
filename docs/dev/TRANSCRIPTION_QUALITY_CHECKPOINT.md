# Transcription Quality Checkpoint

The maintained transcription baseline covers:

- local audio inspection and FFmpeg normalization;
- energy and optional Silero VAD paths;
- Faster-Whisper and explicit mock provider behavior;
- word timestamps and segment alignment;
- conservative Turkish cleanup and glossary resolution;
- selective retranscription candidate selection;
- raw/corrected transcript preservation;
- reference WER/CER and domain-term metrics;
- HTTP and WebSocket compatibility payloads.

Run the focused suite with:

```powershell
python -m pytest tests/transcription -q
```

Run the benchmark and fixture tools with:

```powershell
python scripts/benchmarks/benchmark_transcription_quality.py --help
python scripts/benchmarks/run_project_turkish_transcription_benchmark.py --help
python scripts/datasets/prepare_turkish_audio_fixture.py --help
```

Hardware/model checks skip when prerequisites are absent. Results must report
which provider actually ran and must reject mock fallback as real ASR evidence.

The detailed pre-rework checkpoint is retained at
`docs/archive/pre-rework/TRANSCRIPTION_QUALITY_CHECKPOINT.md`.
