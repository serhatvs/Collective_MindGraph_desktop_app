# 2026-06-30 Reports

This checkpoint groups ASR, transcription benchmark, simulation, and validation planning outputs generated on 2026-06-30.

## GPU ASR

- `gpu-asr/FULL_SCALE_GPU_ASR_TEST_REPORT.md`: full CMG pipeline GPU ASR routing validation with Faster-Whisper CUDA/float16 on local Turkish audio.
- `gpu-asr/CPU_VS_GPU_ASR_BENCHMARK_REPORT.md`: small-model CPU versus GPU runtime comparison.
- `gpu-asr/ASR_ACCURACY_BENCHMARK_REPORT.md`: ASR runtime report; WER/CER were not computed because no human reference transcript was supplied.
- `gpu-asr/SILERO_VAD_ASR_VALIDATION_REPORT.md`: VAD-path validation showing Silero was requested but fell back to EnergyVAD while ASR continued.
- `gpu-asr/REAL_ROOM_AUDIO_VALIDATION_PLAN.md`: future validation plan for real meeting-room Turkish audio.

## Transcription Benchmarks

- `transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK.md`: consolidated MediaSpeech TR benchmark summary.
- `transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK_5FILE.md`: 5-file benchmark run.
- `transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK_50FILE.md`: 50-file benchmark run.
- `transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK_50FILE_MERGED.md`: merged 50-file benchmark analysis.
- `transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK_200FILE.md`: 200-file benchmark run.
- `transcription-benchmarks/PROJECT_TURKISH_TRANSCRIPTION_BENCHMARK.md`: project Turkish benchmark placeholder for future real meeting-room fixtures.

## Simulation

- `simulation/FULL_SCALE_SIMULATION_REPORT.md`: full-scale simulated technical meeting report.
- `simulation/FULL_SCALE_SIMULATION_HISTORY.md`: chronological simulation audit history.
- `simulation/export_simulation.json`: exported simulation payload.

## Validation

Standalone validation summaries for this date can be placed in `validation/`. The current validation plan is ASR-specific and is stored with the GPU ASR reports.

## Known Claim Boundaries

- GPU routing is validated for ASR execution, not end-to-end production meeting-room quality.
- MediaSpeech TR results are clean-speech benchmark results and should not be generalized to noisy meeting rooms.
- WER/CER were not computed for ASR accuracy without a supplied human reference.
- Silero VAD was not successfully validated in the current Windows environment; EnergyVAD fallback kept ASR operational.
- Diarization and robust multi-speaker separation remain unvalidated.
