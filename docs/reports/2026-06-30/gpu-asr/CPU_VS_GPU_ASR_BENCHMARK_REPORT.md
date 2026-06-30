# CPU vs GPU ASR Benchmark Report

Date: 2026-06-30
Status: `CPU_VS_GPU_ASR_BENCHMARK_RUN`

## Claim Boundary

This benchmark compares runtime behavior only. It does not claim transcription accuracy because no reference transcript is required or scored here.

## Summary

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.wav`
- Audio duration: `14.500` seconds
- Model: `small`
- VAD provider: `energy`
- CPU transcription time: `17.904` seconds
- GPU transcription time: `2.131` seconds
- CPU real-time factor: `1.235`
- GPU real-time factor: `0.147`
- CPU segment count: `5`
- GPU segment count: `5`
- GPU fallback status: `False`
- GPU fallback reason: `None`

## CPU Run

- Label: `cpu`
- Profile: `cpu`
- Model: `small`
- Requested VAD provider: `energy`
- Actual VAD provider: `energy`
- Model load time: `3.981` seconds
- Transcription time: `17.904` seconds
- Real-time factor: `1.235`
- Segment count: `5`
- Speech region count: `5`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- GPU requested: `False`
- GPU actually used by ASR: `False`
- GPU fallback happened: `False`
- Fallback reason: `None`
- Error: `None`

Diagnostics:

```text
ASR runtime profile: cpu
ASR backend: auto
ASR backend resolved: faster_whisper
ASR model: small
ASR device: cpu
ASR compute type: int8
ASR language: tr
CMG_GPU_ENABLED: False
CMG_REQUIRE_GPU: False
CUDA available through torch: True
Torch CUDA probe status: cuda_available
Torch version: 2.12.1+cu132
Torch CUDA version: 13.2
Faster-Whisper CUDA load status: not_requested
GPU requested by ASR: False
GPU actually loaded by ASR: False
Fallback happened: False
Fallback reason: None
CUDA DLL directories: ['D:\\Workspace\\Collective-MindGraph-2\\.venv-win\\Lib\\site-packages\\nvidia\\cublas\\bin', 'D:\\Workspace\\Collective-MindGraph-2\\.venv-win\\Lib\\site-packages\\nvidia\\cuda_runtime\\bin', 'D:\\Workspace\\Collective-MindGraph-2\\.venv-win\\Lib\\site-packages\\nvidia\\cuda_nvrtc\\bin', 'D:\\Workspace\\Collective-MindGraph-2\\.venv-win\\Lib\\site-packages\\torch\\lib', 'D:\\Workspace\\Collective-MindGraph-2\\.venv-win\\Lib\\site-packages\\ctranslate2']
Embedding device: cpu
Local LLM enabled: False
LLM provider resolved: none
```

CPU transcript:

```text
Böyle el çizimi olanüstü bir abim.
İlk defa.
Kandone Sultan Süleymanı Süleymaniyesi var, oysa.
Onun selimiyesi var edirne de, mimar sinan yapısı ve türbesiz kirliği, çünkü türbesi Ayasofya oluyor.
yani, Ayasofya.
```

## GPU Run

- Label: `gpu`
- Profile: `gpu_asr`
- Model: `small`
- Requested VAD provider: `energy`
- Actual VAD provider: `energy`
- Model load time: `1.066` seconds
- Transcription time: `2.131` seconds
- Real-time factor: `0.147`
- Segment count: `5`
- Speech region count: `5`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- GPU requested: `True`
- GPU actually used by ASR: `True`
- GPU fallback happened: `False`
- Fallback reason: `None`
- Error: `None`

Diagnostics:

```text
ASR runtime profile: gpu_asr
ASR backend: auto
ASR backend resolved: faster_whisper
ASR model: small
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

GPU transcript:

```text
Böyle el çizimi olanüstü bir abim.
İlk defa.
Kandone Sultan Süleymanı Süleymaniyesi var, oysa.
Onun selimiyesi var edirne de, mimarsinal yapısı ve türbesiz kirliği, çünkü türbesi Ayasofya oluyor.
yani, Ayasofya.
```

## Errors And Warnings

- CPU error: `None`
- GPU error: `None`
- CPU warnings: `['ffmpeg normalization failed; original file used for transcription.']`
- GPU warnings: `['ffmpeg normalization failed; original file used for transcription.']`
