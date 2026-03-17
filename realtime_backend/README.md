# Realtime Multi-Speaker STT Backend

Production-style Python backend for long-form, near-real-time speech-to-text with:

- file/WebSocket ingestion on the backend plus microphone/file client scripts
- online-first ASR via Deepgram with local `faster-whisper` fallback
- VAD
- ASR
- speaker diarization
- word-timestamp-based segment alignment
- speaker stabilization across chunks
- bounded long-recording processing windows
- LLM-based transcript correction
- JSON + readable transcript output
- optional summary, topics, decisions, and action-item extraction
- Amazon Bedrock Nova-based transcript correction with local fallback

## What Is Fully Implemented

- FastAPI API with `/health`, `/transcribe/file`, `/transcript/{id}`, `/summary/{id}`
- WebSocket endpoint at `/transcribe/stream`
- ffmpeg-based audio normalization
- pluggable VAD, ASR, diarization, and LLM modules
- file-backed transcript persistence
- transcript formatting
- structured transcript renderings with raw/corrected text output plus speaker stats
- heuristic summary/topic/decision/action extraction
- transcript quality reporting endpoint
- incremental stream session handling with overlap-based tail replacement
- Amazon Bedrock-first transcript correction with LM Studio/mock fallback behavior for local development
- client scripts for microphone streaming and file upload

## What Is Approximate In The MVP

- Live stream diarization quality depends on processing rolling windows and reprocessing overlap
- long recordings are processed in bounded windows, but very hard speaker shifts across distant windows can still drift
- overlap handling is marked and preserved, but perfect separation is model-limited
- summary/topics/decisions/action-items use heuristics unless a stronger LLM provider is plugged in
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
python -m pip install torch==2.8.0+cu128 torchvision==0.23.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements.txt
```

Notes:

- `pyannote.audio 3.4.0` currently works cleanly here with `torch/torchaudio 2.8.0+cu128`; newer `torchaudio 2.9+` builds break `AudioMetaData` used by pyannote.
- `huggingface-hub` is intentionally kept below `1.0` because `pyannote.audio 3.4.0` still uses the older `use_auth_token` API path.
- Real diarization still requires accepting the gated model terms, but token loading is now automatic from `CMG_RT_PYANNOTE_TOKEN`, `HF_TOKEN`, Hugging Face login cache, or `realtime_backend/.env`.
- The default ASR mode is now `auto`: if `CMG_RT_DEEPGRAM_API_KEY` exists, the backend uses Deepgram Nova-3 first and falls back to local `faster-whisper` if the online call fails.

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

- `CMG_RT_ASR_PROVIDER=auto|deepgram|faster_whisper|mock`
- `CMG_RT_ASR_MODEL=large-v3-turbo`
- `CMG_RT_ASR_DEVICE=cuda`
- `CMG_RT_ASR_COMPUTE_TYPE=float16`
- `CMG_RT_DEEPGRAM_API_KEY=...`
- `CMG_RT_DEEPGRAM_MODEL=nova-3`
- `CMG_RT_DEEPGRAM_DETECT_LANGUAGE=true`
- `CMG_RT_DIARIZER_PROVIDER=pyannote`
- `CMG_RT_PYANNOTE_TOKEN=...`
- `CMG_RT_PIPELINE_MAX_WINDOW_SECONDS=90`
- `CMG_RT_PIPELINE_WINDOW_OVERLAP_SECONDS=2`
- `CMG_RT_LLM_PROVIDER=bedrock_auto_local|bedrock|auto_local|none|mock|ollama|openai_compatible|lmstudio`
- `CMG_RT_BEDROCK_REGION=us-east-1`
- `CMG_RT_BEDROCK_MODEL_ID=us.amazon.nova-2-lite-v1:0`
- `CMG_RT_BEDROCK_PROFILE=default`
- `CMG_RT_LLM_ENDPOINT=http://127.0.0.1:1234/v1`
- `CMG_RT_LLM_MODEL=auto`
- `CMG_RT_LLM_CONTEXT_SEGMENTS=4`
- `CMG_RT_STREAM_BUFFER_RETENTION_SECONDS=24`

## HTTP API

### `GET /health`
Returns provider configuration health, including resolved ASR/LLM providers and local fallbacks when `auto` modes are used.

### `POST /transcribe/file`
Multipart form upload.

Example:

```powershell
curl -X POST "http://127.0.0.1:8080/transcribe/file" `
  -F "upload=@sample.wav" `
  -F "language=en"
```

### `GET /transcript/{id}`
Returns the stored structured transcript together with raw/corrected renderings and speaker stats.

Example response shape:

```json
{
  "transcript": {
    "conversation_id": "conv_123",
    "source": "upload",
    "segments": [
      {
        "segment_id": "seg_123",
        "start": 12.48,
        "end": 15.02,
        "speaker": "Speaker_2",
        "raw_text": "we should ship that next week",
        "corrected_text": "We should ship that next week.",
        "words": [
          {"start": 12.48, "end": 12.71, "word": "we ", "probability": 0.91},
          {"start": 12.72, "end": 13.10, "word": "should ", "probability": 0.94}
        ],
        "confidence": 0.92,
        "speaker_confidence": 1.0,
        "overlap": false,
        "notes": [],
        "metadata": {
          "raw_speaker": "SPEAKER_01",
          "alignment_source": "word_timestamps"
        }
      }
    ]
  },
  "renderings": {
    "raw_text_output": "[00:12.480 - 00:15.020] Speaker_2: we should ship that next week",
    "corrected_text_output": "[00:12.480 - 00:15.020] Speaker_2: We should ship that next week."
  },
  "speaker_stats": [
    {
      "speaker": "Speaker_2",
      "segment_count": 1,
      "speaking_seconds": 2.54,
      "overlap_segments": 0,
      "first_start": 12.48,
      "last_end": 15.02
    }
  ]
}
```

Segment shape:

```json
{
  "segment_id": "seg_123",
  "start": 12.48,
  "end": 15.02,
  "speaker": "Speaker_2",
  "raw_text": "we should ship that next week",
  "corrected_text": "We should ship that next week.",
  "words": [
    {"start": 12.48, "end": 12.71, "word": "we ", "probability": 0.91},
    {"start": 12.72, "end": 13.10, "word": "should ", "probability": 0.94}
  ],
  "confidence": 0.92,
  "speaker_confidence": 1.0,
  "overlap": false,
  "notes": [],
  "metadata": {
    "raw_speaker": "SPEAKER_01",
    "alignment_source": "word_timestamps"
  }
}
```

### `GET /summary/{id}`
Returns summary, topics, decisions, and action items.

### `GET /quality/{id}`
Returns intrinsic transcript quality metrics such as unresolved-speaker count, overlap ratio,
ASR confidence averages, word timestamp coverage, and readability change ratio.

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

Partial and final transcript events now include:

- `segments`
- `text_output`
- `raw_text_output`
- `corrected_text_output`
- `speaker_stats`
- `is_final`

Final transcript events also include:

- `summary`
- `topics`
- `action_items`
- `decisions`

## Suggested RTX 4060 Settings

- ASR mode: `CMG_RT_ASR_PROVIDER=auto` with Deepgram API key if you want online-first behavior
- ASR model: `large-v3-turbo`
- compute type: `float16`
- diarization on GPU if PyTorch CUDA is installed
- LLM mode: `CMG_RT_LLM_PROVIDER=bedrock_auto_local` with AWS credentials if you want Amazon-first correction
- keep stream partial windows around `8-12s`

## Test

```powershell
cd realtime_backend
pytest -q tests
```
