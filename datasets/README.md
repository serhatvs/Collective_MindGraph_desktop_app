# Local Datasets

Everything below `datasets/` is local and ignored except this policy file. Do not commit downloaded corpora, meeting audio, reference transcripts containing personal data, annotation manifests, experiment work directories, or generated exports.

The maintained transcript-reference workflow uses:

```text
datasets/
└── transcription/
    └── <dataset-name>/
        ├── audio/
        ├── references/
        ├── reports/
        └── exports/
```

Create and review datasets with `scripts/launch/launch_transcript_annotation.py`, run experiments with `scripts/datasets/run_transcription_experiments.py`, and export reviewed data with `scripts/datasets/export_transcription_dataset.py`. The dataset format and lifecycle are owned by `tools/transcript_annotation/dataset.py`.

No automatic migration is performed. Existing data already under `datasets/transcription/` remains valid. Data stored elsewhere may remain external and be passed by path, or may be moved here manually after checking privacy and disk-space requirements.
