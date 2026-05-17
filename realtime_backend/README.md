# Realtime Multi-Speaker STT Backend

Production-style Python backend for long-form, near-real-time speech-to-text with:

- file/WebSocket ingestion on the backend plus microphone/file client scripts
- Local ASR via local `faster-whisper`
- VAD
- ASR
- speaker diarization
- word-timestamp-based segment alignment
- speaker stabilization across chunks
- bounded long-recording processing windows
- LLM-based transcript correction (via local providers like LM Studio)
- JSON + readable transcript output
- optional summary, topics, decisions, and action-item extraction
- Local-first transcript correction with mock fallback behavior for local development

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
- The default ASR mode is now `auto`: the backend uses local `faster-whisper`.

## Run

```powershell
cd realtime_backend
uvicorn app.main:app --reload --port 8080
```

## Client Scripts

### Upload a Local File

```powershell
cd realtime_backend
python scripts/transcribe_file.py C:\path\to\conversation.wav --language tr
```

### Stream a Microphone

```powershell
cd realtime_backend
python scripts/stream_microphone.py --language tr
```

Useful flags:

- `--list-devices`
- `--device 1`
- `--flush-seconds 6`

## Key Environment Variables

- `CMG_RT_ASR_PROVIDER=auto|faster_whisper|mock`
- `CMG_RT_ASR_MODEL=large-v3-turbo`
- `CMG_RT_ASR_DEVICE=cuda`
- `CMG_RT_ASR_COMPUTE_TYPE=float16`
- `CMG_RT_DIARIZER_PROVIDER=pyannote`
- `CMG_RT_PYANNOTE_TOKEN=...`
- `CMG_RT_PIPELINE_MAX_WINDOW_SECONDS=90`
- `CMG_RT_PIPELINE_WINDOW_OVERLAP_SECONDS=2`
- `CMG_RT_LLM_PROVIDER=auto_local|none|mock|ollama|openai_compatible|lmstudio`
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
  -F "language=tr"
```

### `GET /transcript/{id}`
Returns the stored structured transcript together with raw/corrected renderings and speaker stats.

### `GET /summary/{id}`
Returns summary, topics, decisions, and action items.

### `GET /quality/{id}`
Returns intrinsic transcript quality metrics such as unresolved-speaker count, overlap ratio,
ASR confidence averages, word timestamp coverage, and readability change ratio.

## WebSocket Streaming

Connect to:

```text
ws://127.0.0.1:8080/transcribe/stream?language=tr
```

The socket returns a `ready` event describing the expected audio format:

- PCM signed 16-bit little-endian
- 16 kHz
- mono

## Suggested RTX 4060 Settings

- ASR mode: `CMG_RT_ASR_PROVIDER=auto`
- ASR model: `large-v3-turbo`
- compute type: `float16`
- diarization on GPU if PyTorch CUDA is installed
- LLM mode: `CMG_RT_LLM_PROVIDER=lmstudio`
- keep stream partial windows around `8-12s`

## Test

```powershell
cd realtime_backend
pytest -q tests
```

## Turkish Support Roadmap
- [ ] Add real Turkish audio fixture test for Faster-Whisper language forcing.

## Turkish transcription status
- **Common Voice Turkish clean-speech benchmark**: ACTIVE
- **Project-specific meeting WAV validation**: OPTIONAL / Pending manual recording
- **All runtime transcription paths use unified TranscriptionPipeline**
- **raw_transcript and cleaned_transcript are preserved separately**
- **Meeting-room accuracy is not claimed yet**

## Testing Turkish transcript quality locally
...
- **raw vs cleaned**: Compare raw ASR output with the LLM-corrected and Turkish-cleaned version to verify filler removal and character preservation.

## Current validation status
- **Common Voice Turkish clean-speech benchmark**: ACTIVE
- **Project-specific meeting sample**: OPTIONAL / Pending manual recording
- **Meeting-room quality**: Not claimed until project sample or real meeting data is tested.
- **Current benchmark metrics**: `keyword_overlap_quality_score` and approximate WER/CER, not final scientific evaluation.

## Testing Turkish ASR with Mozilla Common Voice
...
To perform larger-scale automated testing using the Mozilla Common Voice dataset:

### A. Download Dataset
Download **Common Voice Scripted Speech 25.0 - Turkish** from the Mozilla Common Voice website.
- **Locale**: `tr`
- **License**: `CC0-1.0`

### B. Expected Structure
Extract the dataset so you have a structure like:
```text
tr/
├── clips/
├── test.tsv
├── validated.tsv
└── ...
```

### C. Import Samples
Run the importer to select a subset of samples, convert them to WAV, and generate a manifest:
```powershell
PYTHONPATH=. python scripts/import_common_voice_tr_sample.py /path/to/cv-corpus/tr --num-samples 20 --split test
```

### D. Readiness Check
Verify everything is set up correctly:
```powershell
PYTHONPATH=. python scripts/check_transcription_test_readiness.py
```

### E. Run Automated Tests
```powershell
# Run quick CI-safe regression test (3 samples)
PYTHONPATH=. pytest tests/test_common_voice_tr_asr_quality.py -s

# Run chunk-boundary integration test
PYTHONPATH=. pytest tests/test_common_voice_tr_chunk_boundary.py -s
```

### F. Scalable Local Benchmarking
For a more comprehensive evaluation, use the dedicated benchmark script:
```powershell
# Run benchmark on 20 samples (default smoke test)
PYTHONPATH=. python scripts/benchmark_common_voice_tr.py --num-samples 20 --quality balanced --output-json benchmark_results.json

# Run medium local benchmark (100 samples)
PYTHONPATH=. python scripts/benchmark_common_voice_tr.py --num-samples 100 --quality accurate

# Run full benchmark against all imported manifest samples
PYTHONPATH=. python scripts/benchmark_common_voice_tr.py --num-samples all
```

### G. Understanding Benchmark Metrics
- **keyword_overlap_quality_score**: The percentage of words from the expected sentence found in the transcript. Split into **raw** (pre-cleanup) and **cleaned** (post-cleanup) versions.
- **character_error_rate (CER)**: Approximation of character-level similarity using Levenshtein distance.
- **word_error_rate (WER)**: Approximation of word-level similarity using Levenshtein distance.
- **Scope**:
  - The **Common Voice benchmark** is a clean-speech Turkish ASR regression benchmark. It does not replace noisy meeting-room validation.
  - The default 20-sample run is a **local regression benchmark**, not a full scientific evaluation. 
  - Improvement Delta shows the value added by the LLM and Turkish cleanup layer over the raw ASR output.
- **Diagnostics**: Use the `--output-json` flag to see matched vs. missing terms and individual error rates for every sample.
