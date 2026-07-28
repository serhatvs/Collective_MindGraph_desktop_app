# Repository Scripts

Run scripts from the repository root after installing the package. No script
requires a manual import-path override.

## Launch

| Script | Purpose |
| --- | --- |
| `launch/dev_engine.sh` | Start the localhost development engine. |
| `launch/dev_desktop.sh` | Start the desktop on Bash-compatible systems. |
| `launch/dev_desktop.ps1` | Start the desktop on Windows PowerShell. |
| `launch/launch_cmg.py` | Cross-platform dependency-checking desktop launcher. |
| `launch/launch_transcript_annotation.py` | Open the annotation application. |

Installed commands are preferred for normal use:

```text
mindgraph
mindgraph-engine
mindgraph-annotate
```

## Benchmarks

- `benchmarks/benchmark_asr_accuracy.py`
- `benchmarks/benchmark_common_voice_tr.py`
- `benchmarks/benchmark_cpu_vs_gpu_asr.py`
- `benchmarks/benchmark_selective_retranscription.py`
- `benchmarks/benchmark_transcription_quality.py`
- `benchmarks/run_project_turkish_transcription_benchmark.py`
- `benchmarks/validate_silero_vad_asr.py`

Reference-based tools report WER/CER only when a real reference transcript is
provided. Other scripts report runtime and confidence diagnostics only.

## Datasets and annotation

- `datasets/import_common_voice_tr_sample.py`
- `datasets/prepare_turkish_audio_fixture.py`
- `datasets/export_transcription_dataset.py`
- `datasets/run_transcription_experiments.py`
- `datasets/seed_demo_meeting.py`

Dataset contents and real audio remain local and ignored.

## Operations and validation

`operations/` contains local readiness, graph inspection, microphone streaming,
query, and file-transcription helpers. `validation/` contains GPU and complete
product-loop smoke checks. Both use the canonical package and engine settings.

## Setup and packaging

- `setup/check_demo_readiness.sh`
- `setup/install_friend_alpha_deps.py`
- `packaging/build_windows_exe.ps1`

Generated reports belong under `docs/reports/YYYY-MM-DD/<topic>/`; build output
belongs under ignored `build/` and `dist/`.
