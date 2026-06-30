# Silero VAD ASR Validation Report

Date: 2026-06-30
Status: `SILERO_VAD_ASR_VALIDATION_RUN`

## Scope

This report validates VAD behavior as a separate ASR component. It does not make Silero a requirement for GPU ASR and does not involve diarization.

## Summary

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.wav`
- Audio duration: `14.500` seconds

| Requested VAD | Actual VAD | Status | Speech Segments | ASR GPU Used | Time | Error |
|---|---|---|---:|---|---:|---|
| energy | energy | ok | 5 | True | 2.030 |  |
| silero | energy | silero_unavailable_asr_continued | 5 | True | 1.688 |  |
| none | none | ok | 0 | True | 1.230 |  |

## energy_vad

- Label: `energy_vad`
- Profile: `gpu_asr`
- Model: `small`
- Requested VAD provider: `energy`
- Actual VAD provider: `energy`
- Model load time: `2.541` seconds
- Transcription time: `2.030` seconds
- Real-time factor: `0.140`
- Segment count: `5`
- Speech region count: `5`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- GPU requested: `True`
- GPU actually used by ASR: `True`
- GPU fallback happened: `False`
- Fallback reason: `None`
- Error: `None`

Speech region timestamps:

```text
0.450 -> 2.880
3.090 -> 3.960
4.260 -> 7.350
7.800 -> 11.490
11.610 -> 14.160
```

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

Transcription result:

```text
Böyle el çizimi olanüstü bir abim.
İlk defa.
Kandone Sultan Süleymanı Süleymaniyesi var, oysa.
Onun selimiyesi var edirne de, mimarsinal yapısı ve türbesiz kirliği, çünkü türbesi Ayasofya oluyor.
yani, Ayasofya.
```

## silero_vad

- Label: `silero_vad`
- Profile: `gpu_asr`
- Model: `small`
- Requested VAD provider: `silero`
- Actual VAD provider: `energy`
- Model load time: `0.979` seconds
- Transcription time: `1.688` seconds
- Real-time factor: `0.116`
- Segment count: `5`
- Speech region count: `5`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- GPU requested: `True`
- GPU actually used by ASR: `True`
- GPU fallback happened: `False`
- Fallback reason: `None`
- Error: `None`

Speech region timestamps:

```text
0.450 -> 2.880
3.090 -> 3.960
4.260 -> 7.350
7.800 -> 11.490
11.610 -> 14.160
```

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

Transcription result:

```text
Böyle el çizimi olanüstü bir abim.
İlk defa.
Kandone Sultan Süleymanı Süleymaniyesi var, oysa.
Onun selimiyesi var edirne de, mimarsinal yapısı ve türbesiz kirliği, çünkü türbesi Ayasofya oluyor.
yani, Ayasofya.
```

## no_vad

- Label: `no_vad`
- Profile: `gpu_asr`
- Model: `small`
- Requested VAD provider: `none`
- Actual VAD provider: `none`
- Model load time: `1.006` seconds
- Transcription time: `1.230` seconds
- Real-time factor: `0.085`
- Segment count: `1`
- Speech region count: `0`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- GPU requested: `True`
- GPU actually used by ASR: `True`
- GPU fallback happened: `False`
- Fallback reason: `None`
- Error: `None`

Speech region timestamps:

```text
[no VAD speech regions]
```

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

Transcription result:

```text
Böyle, el çizimi, olağanüstü bir abim, ilk defa Kandone Sultan Süleyman'ı Süleymani'yesi var, oysa onun Selimiyesi var, Edirne'de, Mimar Sinan yapısı ve türbesiz külliye, çünkü türbesi Ayasofya oluyor, yani, Ayasofya.
```
