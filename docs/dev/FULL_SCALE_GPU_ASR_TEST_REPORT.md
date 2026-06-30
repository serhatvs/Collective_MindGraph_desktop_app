# Full-Scale GPU ASR Test Report

Date: 2026-06-30
Status: `FULL_SCALE_GPU_ASR_TEST_RUN`

## Scope

This report validates only the Collective MindGraph ASR/transcription path. It does not validate diarization, graph persistence, Ask Memory, extraction, semantic retrieval, or UI behavior.

## Current Validation Status

- GPU ASR routing: validated.
- Faster-Whisper CUDA: validated through the real CMG backend pipeline.
- `large-v3` + `cuda` + `float16`: validated on a local Turkish WAV.
- `nvidia-smi` observation: validated.
- Silero VAD: not yet validated; a separate validation run showed Silero did not load and ASR continued with EnergyVAD fallback.
- Meeting-room audio: not yet validated.
- Diarization: not implemented/validated.
- WER/CER accuracy: not yet measured in this GPU routing checkpoint.
- Safe claim: Collective MindGraph supports validated GPU-routed local ASR through the real backend transcription pipeline using Faster-Whisper with CUDA/float16.

## ASR Pipeline Path Found

- Desktop file transcription path: `src/collective_mindgraph_desktop/ui/workers.py` or `src/collective_mindgraph_desktop/ui/voice_command_panel.py` -> `RealtimeBackendTranscriptionService.transcribe_file()` -> backend `/transcribe/file`.
- Backend path: `realtime_backend/app/api/routes.py` -> `realtime_backend/app/services/transcription_service.py` -> `realtime_backend/app/pipeline/orchestrator.py` -> `realtime_backend/app/pipeline/asr.py`.
- Real ASR backend: `FasterWhisperASR`, which constructs `faster_whisper.WhisperModel`.
- Vosk usage found only in `src/collective_mindgraph_desktop/wake_phrase.py` for wake phrase detection, not for file transcription ASR.
- Previous GPU env mismatch: backend settings read `CMG_RT_ASR_*` but did not read `CMG_ASR_*` or `CMG_RUNTIME_PROFILE`, so the pasted launch variables could be ignored unless matching `CMG_RT_*` variables were also set.
- Current fix: `realtime_backend/app/pipeline/asr_runtime_config.py` resolves `CMG_RUNTIME_PROFILE`, `CMG_GPU_ENABLED`, `CMG_REQUIRE_GPU`, `CMG_ASR_*`, and existing `CMG_RT_*` aliases.

## GPU Smoke Test

- Command used: `scripts/check_asr_gpu.py --observation-seconds 30` with `CMG_RUNTIME_PROFILE=gpu_asr`, `CMG_REQUIRE_GPU=1`, `CMG_ASR_MODEL=small`, `CMG_ASR_DEVICE=cuda`, and `CMG_ASR_COMPUTE_TYPE=float16`.
- Result: smoke test exited successfully.
- CMG ASR backend resolved to `faster_whisper`.
- Faster-Whisper CUDA load status: `loaded_on_cuda`.
- GPU requested by ASR: `True`.
- GPU actually loaded by ASR: `True`.
- Fallback happened: `False`.
- `nvidia-smi` observed a Python process during the smoke window.

## Dependency Fix Applied

- Initial full-scale large-v3 transcription failed at inference with `RuntimeError: Library cublas64_12.dll is not found or cannot be loaded`.
- Installed venv-local CUDA runtime packages: `nvidia-cublas-cu12`, `nvidia-cuda-runtime-cu12`, and `nvidia-cuda-nvrtc-cu12`.
- Added Windows DLL directory registration in `realtime_backend/app/pipeline/asr_runtime_config.py`.
- `FasterWhisperASR` now registers venv-local CUDA DLL directories before loading Faster-Whisper/CTranslate2.

## Runtime Configuration

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.wav`
- Audio duration: `14.500` seconds
- ASR backend: `auto`
- ASR model: `large-v3`
- ASR device: `cuda`
- ASR compute type: `float16`
- ASR language: `tr`
- Runtime profile: `gpu_asr`
- VAD provider: `energy`
- Diarization enabled: `False`
- Local LLM provider: `none`

## ASR Diagnostics

```text
ASR runtime profile: gpu_asr
ASR backend: auto
ASR backend resolved: faster_whisper
ASR model: large-v3
ASR device: cuda
ASR compute type: float16
ASR language: tr
CMG_GPU_ENABLED: True
CMG_REQUIRE_GPU: True
CUDA available through torch: True
Torch CUDA probe status: cuda_available
Torch version: 2.12.1+cu132
Torch CUDA version: 13.2
Faster-Whisper CUDA load status: loaded_on_cuda
GPU requested by ASR: True
GPU actually loaded by ASR: True
Fallback happened: False
Fallback reason: None
CUDA DLL directories: ['D:\\Workspace\\Collective-MindGraph-2\\.venv-win\\Lib\\site-packages\\nvidia\\cublas\\bin', 'D:\\Workspace\\Collective-MindGraph-2\\.venv-win\\Lib\\site-packages\\nvidia\\cuda_runtime\\bin', 'D:\\Workspace\\Collective-MindGraph-2\\.venv-win\\Lib\\site-packages\\nvidia\\cuda_nvrtc\\bin', 'D:\\Workspace\\Collective-MindGraph-2\\.venv-win\\Lib\\site-packages\\torch\\lib', 'D:\\Workspace\\Collective-MindGraph-2\\.venv-win\\Lib\\site-packages\\ctranslate2']
Embedding device: cpu
Local LLM enabled: False
LLM provider resolved: none
```

## Result

- Transcription time: `48.897` seconds
- Real-time factor: `3.372`
- Segment count: `4`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- GPU requested: `True`
- GPU actually loaded: `True`
- GPU fallback happened: `False`
- Fallback reason: `None`
- nvidia-smi observed this Python process: `True`

## Turkish Character Preservation Check

- `ç`: raw=True, cleaned=True
- `ğ`: raw=True, cleaned=True
- `ı`: raw=True, cleaned=True
- `İ`: raw=False, cleaned=False
- `ö`: raw=True, cleaned=True
- `ş`: raw=False, cleaned=False
- `ü`: raw=True, cleaned=True

## Raw Transcript

```text
böyle el çizimi olağanüstü bir abim
ilk defa
Kanuni Sultan Süleyman'ın Süleymaniye'si var, oysa
onun Selimiyesi var Edirne'de, mimarsinal yapısı ve türbesiz külliye, çünkü türbesiz Ayasofya oluyor.
```

## Cleaned Transcript

```text
Böyle el çizimi olağanüstü bir abim.
Ilk defa.
Kanuni Sultan Süleyman'ın Süleymaniye'si var, oysa.
Onun Selimiyesi var Edirne'de, mimarsinal yapısı ve türbesiz külliye, çünkü türbesiz Ayasofya oluyor.
```

## nvidia-smi Evidence

After model load:

```text
13276, C:\Program Files\WindowsApps\OpenAI.Codex_26.623.8305.0_x64__2p2nqsd0c76g0\app\Codex.exe, [N/A]
11456, C:\Users\Serhat\AppData\Local\Programs\Python\Python313\python.exe, [N/A]
```

After transcription:

```text
13276, C:\Program Files\WindowsApps\OpenAI.Codex_26.623.8305.0_x64__2p2nqsd0c76g0\app\Codex.exe, [N/A]
11456, C:\Users\Serhat\AppData\Local\Programs\Python\Python313\python.exe, [N/A]
```

## Manual Observation Instructions

Terminal 1:

```cmd
set CMG_RUNTIME_PROFILE=gpu_asr
set CMG_GPU_ENABLED=1
set CMG_REQUIRE_GPU=1
set CMG_ASR_DEVICE=cuda
set CMG_ASR_COMPUTE_TYPE=float16
set CMG_ASR_MODEL=small
set CMG_ASR_LANGUAGE=tr
set CMG_EMBEDDING_DEVICE=cpu
set PYTHONPATH=%CD%\src;%CD%
python scripts\check_asr_gpu.py
```

Terminal 2:

```cmd
nvidia-smi -l 1
```

Expected if GPU is really used: a Python process appears under GPU processes, VRAM usage rises above idle, and GPU utilization may rise during transcription.

Large-v3 full-scale mode after the small model GPU smoke test passes:

```cmd
set CMG_ASR_MODEL=large-v3
python scripts\full_scale_gpu_transcription_test.py --profile gpu_asr --audio recordings\test.wav
```

## Pass/Fail Boundary

- Pass requires the real CMG pipeline to load Faster-Whisper with `device=cuda`, `compute_type=float16`, `language=tr`, and transcribe real audio without mock fallback.
- This report does not prove meeting-room readiness unless the audio is real meeting-room audio.
