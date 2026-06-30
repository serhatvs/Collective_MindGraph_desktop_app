# ASR Accuracy Benchmark Report

Date: 2026-06-30
Status: `ASR_ACCURACY_BENCHMARK_RUNTIME_ONLY_NO_REFERENCE`

## Claim Boundary

WER/CER are computed only when a real human reference transcript is provided. No keyword-overlap accuracy percentage is produced.

## Runtime Metrics

- Label: `accuracy`
- Profile: `gpu_asr`
- Model: `small`
- Requested VAD provider: `energy`
- Actual VAD provider: `energy`
- Model load time: `2.544` seconds
- Transcription time: `2.010` seconds
- Real-time factor: `0.139`
- Segment count: `5`
- Speech region count: `5`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- GPU requested: `True`
- GPU actually used by ASR: `True`
- GPU fallback happened: `False`
- Fallback reason: `None`
- Error: `None`
- Audio path: `C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.wav`
- Audio duration: `14.500` seconds
- Reference path: `None`
- Reference transcript provided: `False`
- WER: `not computed`
- CER: `not computed`

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

## Reference Transcript

```text
[not provided]
```

## Raw Transcript

```text
böyle el çizimi olanüstü bir abim
İlk defa
Kandone Sultan Süleymanı Süleymaniyesi var, oysa
onun selimiyesi var edirne de, mimarsinal yapısı ve türbesiz kirliği, çünkü türbesi Ayasofya oluyor.
Yani, Ayasofya...
```

## Cleaned Transcript

```text
Böyle el çizimi olanüstü bir abim.
İlk defa.
Kandone Sultan Süleymanı Süleymaniyesi var, oysa.
Onun selimiyesi var edirne de, mimarsinal yapısı ve türbesiz kirliği, çünkü türbesi Ayasofya oluyor.
yani, Ayasofya.
```

## Accuracy Scoring Status

WER/CER were not computed because no real reference transcript was provided.
