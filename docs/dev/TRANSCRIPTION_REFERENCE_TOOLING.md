# Transcription Reference Tooling

## Purpose

This toolkit creates trustworthy, local, human-reviewed Turkish transcription references. It is deliberately separate from the main Collective MindGraph desktop UI and reuses the existing `TranscriptionPipeline` for every ASR candidate and experiment. It does not add cloud services, diarization, speaker inference, fine-tuning, or a second ASR implementation.

The toolkit supports three evidence-based comparisons:

1. balanced first pass;
2. full-recording `max_quality` or another configured strong profile;
3. balanced first pass plus selective recovery.

Candidate confidence is useful for review prioritization but is not accuracy. WER, CER, and domain-term accuracy are emitted only when reviewed human reference text exists.

## Installation and Launch

Install the desktop and local backend dependencies in the same Python environment used by Collective MindGraph:

```powershell
python -m pip install -e ".[dev]"
python -m pip install -r realtime_backend/requirements.txt
```

Launch the standalone annotation application:

```powershell
python scripts/launch_transcript_annotation.py
```

Open an existing dataset directly:

```powershell
python scripts/launch_transcript_annotation.py --dataset datasets/transcription/bad_mic_pilot
```

PySide6 Qt Multimedia provides local playback. Initial transcription requires the selected Faster-Whisper model to exist locally; model downloads are disabled. Mock ASR is rejected and the recording is not added if real local ASR cannot run.

## Dataset Directory Structure

Schema version `1.0` uses:

```text
datasets/transcription/<dataset_name>/
├── dataset.json
├── recordings/     # populated only when Copy Audio is explicitly selected
├── references/     # combined reviewed reference text per recording
├── exports/        # reviewed training-data exports
└── reports/        # experiment JSON, CSV, and Markdown reports
```

`datasets/transcription/` is ignored by Git to reduce the risk of committing real recordings, personal data, references, or generated clips. Back up important datasets outside the repository as well.

Audio is not copied by default. External absolute paths are stored when the source is outside the dataset; relative paths are used when practical. Original audio is never deleted, rewritten, denoised, or embedded as base64.

## Manifest Schema

Top-level `dataset.json` fields:

- `schema_version`, `dataset_name`, `created_at`, `updated_at`, and `language`;
- deterministic `normalization_policy`;
- `glossary_references`;
- `annotation_statistics`;
- `recordings`.

Each recording preserves:

- `recording_id`, path, SHA-256, meeting/source identifiers, duration, and sample rate;
- recording annotation status;
- recording-condition tags, microphone/room information, and reviewer notes;
- original profile and complete original transcription metadata;
- immutable ASR candidates and segment records.

Each segment keeps separate:

- immutable `original_start`, `original_end`, and `raw_asr_text`;
- `selected_asr_text` and `cleaned_asr_text`;
- editable `reviewed_start`, `reviewed_end`, and `reference_text`;
- `pending`, `reviewed`, `unclear`, or `excluded` status;
- reviewer notes, exclusion reason, confidence metadata, selective-retranscription metadata, warnings, and timestamps.

Retranscribing a recording adds a candidate or experiment result. It never overwrites human reference text.

## Annotation Workflow

1. Create or open a dataset.
2. Add one or more audio files.
3. Choose the initial profile; `balanced` is the default.
4. Choose whether to copy audio. **No** keeps the source path only.
5. Tag recording conditions and record microphone/room notes.
6. Select a segment, replay it, and correct the human-reference field to exactly what was spoken.
7. Adjust reviewed boundaries when necessary. Values are clamped to the recording duration; invalid order is rejected and neighboring overlap is shown as a warning.
8. Mark the segment reviewed, unclear, or excluded.
9. Continue until progress shows the desired review coverage.

Edits autosave through atomic manifest replacement. Combined reference files contain only non-empty reviewed, non-excluded segments. Pending ASR text is never eligible for export.

## Playback and Keyboard Shortcuts

| Action | Shortcut |
| --- | --- |
| Play/pause | `Space` |
| Replay current reviewed segment | `R` |
| Previous segment | `Alt+Left` |
| Next segment | `Alt+Right` |
| Save segment | `Ctrl+S` |
| Mark unclear | `U` |
| Exclude segment | `X` |

The playback controls also provide seeking, current time, segment boundaries, and optional `0.75×` speed. Slower playback does not modify stored audio.

## Recording-Condition Tags

Built-in tags are:

```text
good_mic, bad_mic, far_field, near_field, noisy_room, quiet_room,
low_volume, clipping, echo, phone_recording, laptop_microphone,
external_microphone, overlapping_speech, technical_meeting
```

Comma-separated custom tags are allowed and normalized to lowercase underscore form.

## Normalization and Metrics

The shared module is `realtime_backend/app/evaluation/transcription_metrics.py`. Default Turkish normalization:

- Unicode NFC normalization;
- Turkish-aware lowercase (`I → ı`, `İ → i`);
- apostrophe-variant normalization;
- punctuation removal;
- whitespace collapse;
- no Turkish-character transliteration;
- optional deterministic Turkish integer normalization.

Reports preserve both exact raw comparison and normalized comparison. WER is word-level Levenshtein edits divided by reference words. CER is character-level edits divided by reference characters. Substitutions, deletions, insertions, and reference/hypothesis counts are preserved. Corpus metrics sum errors and reference denominators; they are not an average of per-file percentages.

Domain-term accuracy counts occurrences in the human reference and checks the corresponding aligned hypothesis position. A glossary term occurring elsewhere in the hypothesis does not receive credit. Reports include correct, missing, substituted, and per-term occurrence details.

## Experiment Runner

Balanced only:

```powershell
python scripts/run_transcription_experiments.py --dataset datasets/transcription/bad_mic_pilot --profiles balanced --output datasets/transcription/bad_mic_pilot/reports
```

Full strong pass:

```powershell
python scripts/run_transcription_experiments.py --dataset datasets/transcription/bad_mic_pilot --profiles max_quality --model-override max_quality=large-v3 --output datasets/transcription/bad_mic_pilot/reports
```

Selective recovery only:

```powershell
python scripts/run_transcription_experiments.py --dataset datasets/transcription/bad_mic_pilot --only-selective --model-override selective_recovery=large-v3 --output datasets/transcription/bad_mic_pilot/reports
```

All three modes, filtered to bad microphones, resuming completed runs:

```powershell
python scripts/run_transcription_experiments.py --dataset datasets/transcription/bad_mic_pilot --profiles balanced max_quality --include-selective --condition bad_mic --model-override max_quality=large-v3 --model-override selective_recovery=large-v3 --output datasets/transcription/bad_mic_pilot/reports --resume
```

Additional filters include repeatable `--recording-id`, repeatable `--condition`, and `--max-recordings`. Model overrides use `PROFILE=MODEL`.

Outputs:

- `experiment_results.json`: complete reproducibility and transcript metadata;
- `experiment_results.csv`: comparison table;
- `TRANSCRIPTION_EXPERIMENT_REPORT.md`: dataset/configuration summaries, per-recording and corpus metrics, condition regressions, failures, exclusions, and limitations.

When references exist, the best configuration is ranked by WER, CER, domain-term accuracy, then processing cost. No best configuration is declared from heuristic confidence alone.

## Dataset Export

Export all formats:

```powershell
python scripts/export_transcription_dataset.py --dataset datasets/transcription/bad_mic_pilot --formats csv jsonl hf --output datasets/transcription/bad_mic_pilot/exports/reviewed
```

Individual formats:

```powershell
python scripts/export_transcription_dataset.py --dataset datasets/transcription/bad_mic_pilot --formats csv
python scripts/export_transcription_dataset.py --dataset datasets/transcription/bad_mic_pilot --formats jsonl
python scripts/export_transcription_dataset.py --dataset datasets/transcription/bad_mic_pilot --formats hf
```

Only reviewed, non-empty, non-excluded segments with valid boundaries are exported. Clips are derived from source audio as mono 16 kHz PCM WAV without aggressive denoising. CSV uses the requested `audio`, `sentence`, recording/meeting/segment identifiers, boundaries, conditions, and `speaker_id`; speaker defaults to `unknown` and is never inferred. JSONL preserves additional source metadata and hashes. The Hugging Face AudioFolder directory contains `audio/*.wav` plus `metadata.csv`. `export_validation.json` records exported/skipped counts, warnings, and format details.

## Integrity, Privacy, and Backups

- Source and exported audio SHA-256 values are recorded.
- Duplicate source audio and segment IDs are rejected.
- Missing audio, hash mismatches, invalid boundaries, and empty reviewed references are reported.
- Manifest/reference/result writes use same-directory temporary files followed by atomic replacement.
- A timestamped `dataset.json.backup-*` is created before schema migration.
- Unknown future schema versions are rejected without overwriting the manifest.
- Original audio and immutable ASR fields are never overwritten.

All recordings and references stay local. They may contain personal or confidential speech; obtain consent, minimize retention, control filesystem access, and never commit datasets, exports, or private glossary files.

## Known Limitations and Fine-Tuning Preparation

Playback is timeline/numeric-boundary based, not a waveform editor. No speaker identity is inferred; use `unknown` unless a human supplies a label. Segment-to-candidate comparison uses reviewed time intervals and may need manual inspection when profiles produce very different segmentation.

This task does not fine-tune Whisper. Before later fine-tuning, collect representative human-reviewed data, keep training/development/evaluation meeting IDs disjoint, validate export hashes and boundaries, compare stock models on the held-out set, and document consent and licensing.
