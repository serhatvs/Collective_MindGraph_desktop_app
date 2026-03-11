# Realtime Multi-Speaker STT Backend

Production-style Python backend for long-form, near-real-time speech-to-text with:

- file/WebSocket ingestion on the backend plus microphone/file client scripts
- VAD
- ASR
- speaker diarization
- speaker stabilization across chunks
- LLM-based transcript correction
- JSON + readable transcript output
- optional summary, topics, and action-item extraction

## What Is Fully Implemented

- FastAPI API with `/health`, `/transcribe/file`, `/transcript/{id}`, `/summary/{id}`
- WebSocket endpoint at `/transcribe/stream`
- ffmpeg-based audio normalization
- pluggable VAD, ASR, diarization, and LLM modules
- file-backed transcript persistence
- transcript formatting
- incremental stream session handling with overlap-based tail replacement
- mock/no-op LLM providers for testing and local development
- client scripts for microphone streaming and file upload

## What Is Approximate In The MVP

- Live stream diarization quality depends on processing rolling windows and reprocessing overlap
- overlap handling is marked and preserved, but perfect separation is model-limited
- summary/topics/action-items use heuristic extraction unless a stronger LLM provider is plugged in
- the websocket path expects `pcm_s16le`, mono, `16 kHz` chunks

## Recommended Install Flow

1. Install Python 3.11+
2. Install ffmpeg and add it to `PATH`
3. Install an appropriate CUDA-enabled PyTorch build for your GPU if you want GPU diarization/ASR
4. Install backend dependencies

```powershell
cd realtime_backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

```powershell
cd realtime_backend
uvicorn app.main:app --reload --port 8080
```

## Client Scripts

### Upload a Local File

```powershell
cd realtime_backend
python scripts/transcribe_file.py C:\path\to\conversation.wav --language en
```

### Stream a Microphone

```powershell
cd realtime_backend
python scripts/stream_microphone.py --language en
```

Useful flags:

- `--list-devices`
- `--device 1`
- `--flush-seconds 6`

## Key Environment Variables

- `CMG_RT_ASR_MODEL=distil-large-v3`
- `CMG_RT_ASR_DEVICE=cuda`
- `CMG_RT_ASR_COMPUTE_TYPE=float16`
- `CMG_RT_DIARIZER_PROVIDER=pyannote`
- `CMG_RT_PYANNOTE_TOKEN=...`
- `CMG_RT_LLM_PROVIDER=mock|none|ollama|openai_compatible`
- `CMG_RT_LLM_ENDPOINT=http://127.0.0.1:11434/api/generate`
- `CMG_RT_LLM_MODEL=llama3.1`

## HTTP API

### `GET /health`
Returns provider configuration health.

### `POST /transcribe/file`
Multipart form upload.

Example:

```powershell
curl -X POST "http://127.0.0.1:8080/transcribe/file" `
  -F "upload=@sample.wav" `
  -F "language=en"
```

### `GET /transcript/{id}`
Returns the stored structured transcript.

### `GET /summary/{id}`
Returns summary, topics, and action items.

## WebSocket Streaming

Connect to:

```text
ws://127.0.0.1:8080/transcribe/stream?language=en
```

The socket returns a `ready` event describing the expected audio format:

- PCM signed 16-bit little-endian
- 16 kHz
- mono

Events:

- send binary frames with PCM audio
- send `{"event":"flush"}` for an incremental update
- send `{"event":"finalize"}` for final transcript + summary

## Suggested RTX 4060 Settings

- ASR model: `distil-large-v3` or `large-v3-turbo`
- compute type: `float16`
- diarization on GPU if PyTorch CUDA is installed
- keep stream partial windows around `8-12s`

## Test

```powershell
cd realtime_backend
pytest -q tests
```
