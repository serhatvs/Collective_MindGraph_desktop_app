# Transcription Quality V2 Report

Status: `NOT_RUN`

No benchmark audio has been run in this branch yet.

Run:

```powershell
$env:PYTHONPATH='src;.'
python scripts/benchmark_transcription_quality_v2.py C:\path\audio.wav --profiles fast balanced max_quality bad_mic_recovery
```

The generated report will include file name, duration, profile, model/settings, processing time, transcript, confidence estimate, audio quality score, warnings, and manual-review notes.
