# Transcription Quality V2

## Why This Branch Exists

Friend alpha produced useful signal: bad microphone conditions can land around a rough 60% transcription quality result in practice. This branch treats that as the next core technical development track, not as an alpha scope issue to explain away.

The focus is local transcription quality for noisy, low-volume, and weak-microphone audio. This track intentionally excludes LLM features, diarization, speaker separation, memory graph work, Ask Memory work, UI redesign, hardware changes, and cloud APIs.

## Profiles

Profiles are selected with `quality_mode` on `/transcribe/file` or with `CMG_RT_TRANSCRIPTION_QUALITY_MODE`.

- `fast`: quick testing, low latency, beam `1`, no word timestamps by default, format-only preprocessing.
- `balanced`: practical default candidate, beam at least `3`, word timestamps when enabled, safe loudness preprocessing.
- `max_quality`: best general quality when the user can wait, stronger beam, temperature fallback, safe loudness preprocessing.
- `bad_mic_recovery`: weak/noisy/low-volume microphone recovery, stronger beam, word timestamps, higher no-speech tolerance, stronger safe preprocessing.

Model and compute type remain configurable. Optional profile-specific environment variables:

- `CMG_RT_ASR_FAST_MODEL`
- `CMG_RT_ASR_BALANCED_MODEL`
- `CMG_RT_ASR_MAX_QUALITY_MODEL`
- `CMG_RT_ASR_BAD_MIC_MODEL`
- `CMG_RT_ASR_FAST_COMPUTE_TYPE`
- `CMG_RT_ASR_BALANCED_COMPUTE_TYPE`
- `CMG_RT_ASR_MAX_QUALITY_COMPUTE_TYPE`
- `CMG_RT_ASR_BAD_MIC_COMPUTE_TYPE`

Bad-mic preprocessing options:

- `CMG_RT_ASR_SAFE_SILENCE_TRIM=true`
- `CMG_RT_ASR_BAD_MIC_NOISE_REDUCTION=false`

## Confidence Percentage

`Transcription Confidence Estimate` is a 0-100 operational estimate. It combines:

- audio quality score
- Faster-Whisper segment metadata such as confidence, `avg_logprob`, `no_speech_prob`, and `compression_ratio`
- empty or very short segment ratio
- transcript length sanity against audio duration
- basic Turkish text sanity when language is `tr`

It is not real accuracy. It is not WER or CER. Real accuracy requires a human reference transcript aligned to the same audio.

## Audio Quality Score

The audio analyzer estimates:

- duration
- RMS and dBFS loudness
- peak level
- silence ratio
- clipping ratio
- unstable level ratio
- possible noisy/unclear audio
- preprocessing applied and preprocessing steps

Labels:

- `High`: 75-100
- `Medium`: 50-74
- `Low`: 0-49

## Run Profiles

Use the backend API with a `quality_mode` form field:

```powershell
curl -F "upload=@C:\path\audio.wav" -F "language=tr" -F "quality_mode=bad_mic_recovery" http://127.0.0.1:8080/transcribe/file
```

Or set:

```powershell
$env:CMG_RT_TRANSCRIPTION_QUALITY_MODE='bad_mic_recovery'
```

## Run Benchmark

```powershell
$env:PYTHONPATH='src;.'
python scripts/benchmarks/benchmark_transcription_quality_v2.py C:\path\audio1.wav C:\path\audio2.wav --profiles fast balanced max_quality bad_mic_recovery
```

The script writes:

```text
docs/dev/TRANSCRIPTION_QUALITY_V2_REPORT.md
```

## Recommended Next Experiments

- Record real bad-mic Turkish meeting fixtures with human reference transcripts.
- Compare `balanced`, `max_quality`, and `bad_mic_recovery` on the same audio with WER/CER only when references exist.
- Test whether `CMG_RT_ASR_BAD_MIC_NOISE_REDUCTION=true` helps or harms weak-microphone Turkish speech.
- Compare `large-v3`, `large-v3-turbo`, and the current alpha model under the same bad-mic fixtures.
- Tune VAD padding and no-speech thresholds against missed quiet words, not clean test speech.
