# Project Turkish Audio Fixture Guide

Date: 2026-06-22

Scope: local Turkish transcription quality fixtures only. Do not use cloud STT, cloud LLMs, or external transcription services to create benchmark references.

## Goal

Create local audio fixtures that can fairly test Turkish speech-to-text quality for Collective MindGraph.

Save project fixtures under:

```text
realtime_backend/tests/fixtures/audio/project_turkish/
realtime_backend/tests/fixtures/expected/project_turkish/
```

Recommended naming:

```text
realtime_backend/tests/fixtures/audio/project_turkish/clean_nearfield_001.wav
realtime_backend/tests/fixtures/expected/project_turkish/clean_nearfield_001.reference.txt

realtime_backend/tests/fixtures/audio/project_turkish/real_meeting_room_001.wav
realtime_backend/tests/fixtures/expected/project_turkish/real_meeting_room_001.reference.txt
```

## Fixture Types

### 1. Clean Near-Field Speech

Purpose: quick sanity check for Turkish characters, technical terms, punctuation, and model/profile regressions.

Recommended recording:

- 1-3 minutes.
- One speaker.
- Microphone close to the speaker.
- Quiet room.
- Natural Turkish speech, not exaggerated dictation.
- Include technical terms:
  - Collective MindGraph
  - FastAPI
  - SQLite
  - PySide6
  - VAD
  - transcript
  - aksiyon
  - karar

### 2. Real Meeting-Room Audio

Purpose: the actual readiness benchmark.

Recommended recording:

- 5-10 minutes.
- Real room acoustics.
- Two or more people if possible.
- Laptop or meeting-room microphone.
- Natural turn-taking.
- Some hesitations and filler words.
- Include Turkish characters naturally: ç, ğ, ı, İ, ö, ş, ü.

This is the fixture needed before claiming real Turkish meeting-room readiness.

### 3. Noisy Room Sample

Purpose: test VAD and ASR behavior under realistic background noise.

Recommended recording:

- 1-3 minutes.
- Background fan, HVAC, keyboard, hallway noise, or cafe-like room noise.
- Keep speech intelligible to a human listener.
- Record without noise suppression if possible, so preprocessing weaknesses remain visible.

### 4. Optional Overlapping Speech Sample

Purpose: expose ASR degradation during interruption or simultaneous speech.

Recommended recording:

- 30-90 seconds is enough.
- Two speakers briefly overlap.
- Human reference should mark overlap in plain text notes.
- Do not treat this as diarization validation; use it only to inspect text transcription quality.

## Reference Transcript Rules

Write the reference manually by listening to the audio.

Do:

- Preserve Turkish characters.
- Preserve meaningful filler words such as `şey`, `yani`, and `işte`.
- Include technical terms in their intended spelling.
- Mark inaudible content as `[inaudible]`.
- Use simple punctuation if helpful.
- Keep the text faithful rather than polished.

Do not:

- Use cloud transcription.
- Use OpenAI Whisper API or any remote STT service.
- Use cloud LLMs to repair the reference.
- Create a reference from the system output.
- Remove filler words just because they look messy.

## Audio Format

Preferred:

```text
WAV, mono or stereo, 16 kHz or 48 kHz, 16-bit PCM
```

Accepted:

```text
Any local ffmpeg-readable audio format
```

Notes:

- WAV is easiest to inspect.
- Keep the original recording if possible.
- Avoid automatic gain, denoise, or speech enhancement unless the test specifically targets processed audio.
- Record the microphone, distance, room, speaker count, and noise conditions in a short sidecar note if possible.

## Raw vs Cleaned Outputs

When running the benchmark, save both:

- raw ASR transcript
- conservative cleaned transcript

Raw ASR is the primary evidence for speech-to-text quality.

Cleaned transcript is useful for readability, but it should not hide ASR mistakes.

## Running The Benchmark

Example:

```powershell
python scripts/run_project_turkish_transcription_benchmark.py `
  --audio realtime_backend/tests/fixtures/audio/project_turkish/real_meeting_room_001.wav `
  --reference realtime_backend/tests/fixtures/expected/project_turkish/real_meeting_room_001.reference.txt `
  --audio-kind real_meeting_room `
  --output docs/dev/PROJECT_TURKISH_TRANSCRIPTION_BENCHMARK.md
```

The benchmark compares:

- `large-v3 + max_quality`
- `large-v3 + balanced`
- `large-v3-turbo + max_quality`
- `large-v3-turbo + balanced`

It forces:

- `language=tr`
- `transcript_cleanup_mode=conservative`
- Faster-Whisper internal VAD disabled
- external VAD requested as Silero
- no cloud APIs
- no LLM correction

If the report shows `ASR_STATUS=MOCK_FALLBACK`, the result is invalid.

## What Counts As Evidence

Good evidence:

- Real local audio.
- Human reference transcript.
- WER/CER from the benchmark.
- Raw and cleaned transcript review.
- VAD clipping notes plus manual listening.

Not enough evidence:

- Common Voice only.
- Clean one-speaker speech only.
- No reference transcript.
- Mock fallback output.
- A visually plausible cleaned transcript without raw ASR review.
