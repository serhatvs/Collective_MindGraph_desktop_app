# Transcription Fixture Drop Zone

Place the real Turkish meeting-room validation fixture here:

```text
tests/fixtures/transcription/tr_meeting_room_sample.wav
tests/fixtures/transcription/tr_meeting_room_reference.txt
```

Rules:

- Use a real local meeting-room recording only if it is intended to be stored in the repo.
- Write the reference transcript manually by listening to the audio.
- Preserve Turkish characters and meaningful filler words.
- Do not use cloud STT or a cloud LLM to create or repair the reference transcript.
- Do not commit private or sensitive meeting audio unless it has been explicitly cleared as a test fixture.

Preferred audio format: WAV, 16-bit PCM, mono or stereo, 16 kHz or 48 kHz.

Validation command:

```powershell
.\.venv-win\Scripts\python.exe scripts\benchmark_asr_accuracy.py --audio tests\fixtures\transcription\tr_meeting_room_sample.wav --reference tests\fixtures\transcription\tr_meeting_room_reference.txt --quality-mode balanced --output docs\reports\2026-06-30\TR_MEETING_ROOM_TRANSCRIPTION_VALIDATION.md
```
