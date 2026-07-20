# Selective Retranscription Benchmark Report

Status: `BENCHMARK_NOT_RUN_NO_USER_BAD_MIC_AUDIO`

The implementation and mock-driven integration tests are present, but no new real bad-microphone recording with a human reference transcript was supplied for this branch. No WER, CER, or accuracy improvement is claimed.

Run a reference-based comparison with:

```powershell
python scripts/benchmarks/benchmark_selective_retranscription.py C:\audio\meeting.wav --reference C:\audio\meeting.txt --first-pass-profile balanced --second-pass-profile selective_recovery --output docs/reports/2026-07-19/transcription-benchmarks/SELECTIVE_RETRANSCRIPTION_REPORT.md
```
