# Repository Scripts

Tracked scripts are grouped by operational purpose. Run commands from the repository root unless a row explicitly says that the caller's working directory is irrelevant. Launchers and setup wrappers resolve the repository root from their own file location, so they are safe to invoke from any working directory.

| Script | Purpose and maintained caller | Output or side effect |
| --- | --- | --- |
| `launch/dev_backend.sh` | Maintained Bash development entry point for the FastAPI backend; used by developers and demo docs. | Starts Uvicorn on localhost; no generated file. |
| `launch/dev_desktop.sh` | Maintained Bash development entry point for the PySide6 desktop app. | Starts the desktop process; no generated file. |
| `launch/dev_desktop.ps1` | Maintained Windows PowerShell development entry point for the desktop app. | Starts the desktop process; no generated file. |
| `launch/launch_cmg.py` | Maintained cross-platform friend-alpha desktop launcher; called directly and by `launch_cmg.bat`. | Starts the desktop process after dependency checks. |
| `launch/launch_cmg.bat` | Maintained Windows double-click wrapper for `launch_cmg.py`. | Starts the Python launcher. |
| `launch/launch_transcript_annotation.py` | Maintained entry point for the reusable transcript annotation tool in `tools/transcript_annotation/`. | Opens the annotation UI; dataset changes occur only at the user-selected dataset path. |
| `benchmarks/asr_benchmark_common.py` | Maintained shared helper for the ASR benchmark scripts; not a standalone CLI. | No direct output. |
| `benchmarks/benchmark_asr_accuracy.py` | Maintained reference-based ASR accuracy benchmark. | Writes the selected Markdown report, defaulting under `docs/reports/2026-06-30/gpu-asr/`. |
| `benchmarks/benchmark_cpu_vs_gpu_asr.py` | Maintained CPU/GPU comparison benchmark. | Writes the selected Markdown report under `docs/reports/` by default. |
| `benchmarks/benchmark_selective_retranscription.py` | Maintained comparison of first pass, full strong pass, and selective recovery. | Writes the selected Markdown report. |
| `benchmarks/benchmark_transcription_quality_v2.py` | Maintained quality-profile benchmark without unearned WER/CER claims. | Writes the selected Markdown report. |
| `benchmarks/run_project_turkish_transcription_benchmark.py` | Maintained project or external-dataset Turkish ASR benchmark. | Writes a Markdown report under `docs/reports/` by default. |
| `benchmarks/validate_silero_vad_asr.py` | Maintained Energy/Silero/no-VAD comparative benchmark; grouped here because it shares the benchmark harness and produces a report. | Writes the selected Markdown report under `docs/reports/` by default. |
| `datasets/export_transcription_dataset.py` | Maintained reviewed annotation export CLI; used by the reference-tooling workflow. | Writes CSV, JSONL, and/or Hugging Face AudioFolder exports below the dataset root or `--output`. |
| `datasets/run_transcription_experiments.py` | Maintained reproducible experiment runner for annotation datasets. | Writes resumable experiment results below the dataset root or `--output`. |
| `validation/check_asr_gpu.py` | Maintained real-provider GPU routing smoke check. | Prints diagnostics; optionally transcribes caller-supplied local audio. |
| `validation/full_scale_gpu_transcription_test.py` | Maintained end-to-end GPU transcription validation. | Writes the selected Markdown validation report under `docs/reports/` by default. |
| `setup/check_demo_readiness.sh` | Maintained Bash environment readiness check used by demo docs. | Prints readiness status; no generated file. |
| `setup/install_friend_alpha_deps.py` | Maintained friend-alpha dependency bootstrapper. | Installs project/backend Python dependencies into the active environment. |
| `setup/install_friend_alpha_deps.bat` | Maintained Windows double-click wrapper for the Python bootstrapper. | Runs the setup script in the repository root. |
| `packaging/build_windows_exe.ps1` | Maintained PyInstaller build entry point. | Writes ignored `build/` and `dist/` artifacts. |

Backend-only operational scripts remain in `realtime_backend/scripts/` because their package, fixture, and runtime ownership is already unambiguous. No tracked script in this directory is classified as obsolete. Historical references are retained in `docs/archive/`, with command paths migrated to the maintained locations above.
