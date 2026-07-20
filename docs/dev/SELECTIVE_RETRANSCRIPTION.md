# Selective Retranscription

## Purpose

Selective retranscription gives low-confidence raw ASR segments one bounded second pass without retranscribing an entire recording. It is intended for poor microphones, distant or low-volume speech, noise, and difficult Turkish technical vocabulary. The feature is disabled by default until reference-based bad-microphone benchmarks demonstrate a useful quality/runtime tradeoff.

## Pipeline Position

The first pass still uses the normal preprocessing, external VAD, processing windows, and Faster-Whisper provider. Raw `ASRSegment` objects are inspected immediately after the first pass and before timestamp alignment, transcript cleanup, or optional LLM postprocessing. Flagged audio regions are extracted from the waveform passed to ASR, retranscribed with the configured recovery profile, and compared deterministically. Only the selected raw candidate proceeds to alignment and cleanup.

The complete first-pass segments, full raw second-pass candidate segments, selected raw text, scores, trigger reasons, and selection reason remain in `transcript.metadata.selective_retranscription` and per-segment ASR metadata.

## Trigger Logic

A segment is eligible only when its duration falls between the configured minimum and maximum. It can be flagged by:

- low `avg_logprob`;
- high `no_speech_prob`;
- high compression ratio;
- low mean word probability;
- empty or nearly empty raw text;
- abnormally low or high words per second;
- repeated phrase patterns;
- invalid timestamp shape;
- a low aggregate candidate score;
- low-volume, noisy, or low audio-quality signals when the segment is already suspicious.

Padding is clamped to the audio duration and to adjacent unflagged segment boundaries. Adjacent flagged regions are merged only when their gap and combined duration remain within configured bounds. `selective_retranscription_max_regions` is enforced across the whole transcription job, not once per processing window.

## Candidate Scoring

`transcription_candidate_selector.py` scores first- and second-pass raw candidates from measurable ASR and text-shape signals:

- average log probability;
- word probability or segment confidence;
- no-speech probability;
- compression ratio;
- duration/text-rate sanity;
- Turkish text sanity;
- repetition penalty;
- timestamp validity.

The score is an estimated candidate quality score. It is not accuracy, WER, or CER. Transcript length is not rewarded by itself. Glossary terms newly introduced by a second pass receive no bonus; the selector only applies a small penalty when a glossary term already present in the first pass is lost. The second pass replaces the first only when its adjusted score improves by at least `selective_retranscription_min_improvement`.

## Recovery Profile

`selective_recovery` enables word timestamps, disables internal Faster-Whisper VAD for isolated regions, disables previous-text conditioning, uses a larger beam, and enables temperature fallback. Its model is configurable and defaults to `large-v3`; its compute type defaults to `float16` on CUDA and otherwise uses the base ASR compute type.

Faster-Whisper model loading uses `local_files_only` unless remote downloads are explicitly allowed. If the stronger model or extracted region cannot be loaded, the job retains the first-pass transcript and records a fallback reason instead of failing the entire transcription.

## Dynamic Glossary and Hotwords

Glossary resolution order is:

1. user-supplied hotwords;
2. session glossary terms;
3. project glossary file;
4. bundled global Turkish glossary.

Terms are whitespace-normalized and case-insensitively deduplicated. The resolver enforces maximum term count, prompt length, and individual term length. Metadata reports supplied and accepted counts by source, duplicate removals, every omission category, final prompt count, and the project/global file status.

The accepted prompt is sent through `initial_prompt`. When the installed Faster-Whisper method exposes `hotwords`, the same bounded term set is also sent as hotwords. Capability detection and retry logic preserve compatibility with versions that do not support `hotwords`.

File API clients can send `session_glossary` and `hotwords` as JSON arrays or comma/newline-separated strings. Streaming clients can use the same names as WebSocket query parameters. The desktop transcription configuration exposes `session_glossary_terms` and `user_hotwords` without changing the UI.

## Configuration

| Setting | Default |
| --- | --- |
| `selective_retranscription_enabled` | `False` |
| `selective_retranscription_profile` | `selective_recovery` |
| `selective_retranscription_model` | `large-v3` |
| `selective_retranscription_compute_type` | `None` (CUDA `float16`, otherwise base compute type) |
| `selective_retranscription_beam_size` | `10` |
| `selective_retranscription_avg_logprob_threshold` | `-0.75` |
| `selective_retranscription_no_speech_threshold` | `0.55` |
| `selective_retranscription_compression_ratio_threshold` | `2.4` |
| `selective_retranscription_word_probability_threshold` | `0.55` |
| `selective_retranscription_min_segment_duration` | `0.6` seconds |
| `selective_retranscription_padding_seconds` | `0.35` seconds |
| `selective_retranscription_max_segment_duration` | `30.0` seconds |
| `selective_retranscription_merge_gap_seconds` | `0.25` seconds |
| `selective_retranscription_max_regions` | `8` |
| `selective_retranscription_min_improvement` | `6.0` candidate-score points |
| `selective_retranscription_candidate_score_threshold` | `62.0` |
| `selective_retranscription_min_words_per_second` | `0.45` |
| `selective_retranscription_max_words_per_second` | `5.5` |
| `selective_retranscription_min_text_length` | `4` characters |
| `selective_retranscription_audio_quality_threshold` | `60` |
| `transcription_project_glossary_path` | `None` |
| `transcription_glossary_max_terms` | `120` |
| `transcription_glossary_max_prompt_chars` | `1500` |
| `transcription_glossary_max_term_length` | `80` |

Environment variables use the `CMG_RT_` prefix and uppercase setting name, for example `CMG_RT_SELECTIVE_RETRANSCRIPTION_ENABLED=1`.

Disable the feature by leaving `selective_retranscription_enabled=False` or setting `CMG_RT_SELECTIVE_RETRANSCRIPTION_ENABLED=0`.

## Benchmarking

One audio file without a reference:

```powershell
python scripts/benchmarks/benchmark_selective_retranscription.py C:\audio\meeting.wav --first-pass-profile balanced --second-pass-profile selective_recovery --output docs/dev/SELECTIVE_RETRANSCRIPTION_REPORT.md
```

One audio file with a human reference and project glossary:

```powershell
python scripts/benchmarks/benchmark_selective_retranscription.py C:\audio\meeting.wav --reference C:\audio\meeting.txt --glossary-file C:\audio\project_glossary.json --first-pass-profile balanced --second-pass-profile selective_recovery --output docs/dev/SELECTIVE_RETRANSCRIPTION_REPORT.md
```

A directory with same-stem references in a separate directory:

```powershell
python scripts/benchmarks/benchmark_selective_retranscription.py C:\audio\meetings --reference C:\audio\references --first-pass-profile balanced --second-pass-profile selective_recovery --output docs/dev/SELECTIVE_RETRANSCRIPTION_REPORT.md
```

The benchmark compares first pass only, a full-recording strong pass, and selective retranscription. With references it reports WER, CER, term accuracy, edit operations, time, real-time factor, retranscribed-region count, and retranscribed-audio percentage. Without references it omits reference metrics and reports only estimates, candidate scores, warnings, timing, and selected text.

## Performance and Limitations

The added cost is model loading plus ASR time for selected regions. The metadata separates first-pass time, second-pass/additional time, region count, region duration, and percentage of audio retranscribed.

This implementation does not establish improved real-world accuracy. It still requires representative bad-microphone and distant-room Turkish recordings, human reference transcripts, comparison of recovery models and profiles, and evaluation of whether a custom Turkish meeting model or merged/converted LoRA model outperforms stock Whisper. The confidence and candidate scores must not replace WER/CER or human review.
