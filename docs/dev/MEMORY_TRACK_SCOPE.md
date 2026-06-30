# Collective MindGraph - Memory Track Scope

## Branch

```text
feature/transcript-to-memory-pipeline
```

## Purpose

This branch is for the main product development track.

The goal is to turn transcripts into trusted, reviewable, source-linked organizational memory.

## Main pipeline

```text
Transcript Input
-> Raw Transcript
-> Cleaned Transcript
-> Segments
-> Structured Extraction
-> Pending Knowledge Suggestions
-> Human Review
-> Approved / Edited / Rejected / Disabled / Merged Memory
-> Memory Graph Persistence
-> Source References
-> Hybrid Search
-> Evidence Chain
-> Evidence-only Ask Memory
-> Export / Import / Diagnostics
```

## Allowed work

```text
- transcript ingestion
- segment handling
- structured extraction
- task extraction
- decision extraction
- topic extraction
- entity extraction
- risk extraction
- open question extraction
- follow-up extraction
- source references
- graph persistence
- review lifecycle
- evidence-only Ask Memory
- graph reasoning
- hybrid search
- export/import if related to memory
- diagnostics for memory pipeline
```

## Forbidden work

```text
- ASR quality tuning
- audio preprocessing
- ffmpeg normalization
- Faster-Whisper model settings
- VAD tuning
- diarization
- speaker separation
- transcription benchmark logic
- unrelated UI redesign
- hardware/device code
- patent wording
```

## Shared transcript contract

The memory branch consumes transcript output from the transcription branch.

Required transcript shape:

```text
raw_transcript
cleaned_transcript
segments
timestamps
language
source_file or session_id
transcription_profile
metadata
```

Recommended segment shape:

```text
segment_id
start_time
end_time
raw_text
cleaned_text
language
source_reference
```

Rules:

```text
- Memory branch must not care how ASR produced the transcript.
- Memory branch must not tune ASR/audio.
- Memory branch must preserve source traceability.
- No memory item should exist without a source reference.
```

## Diarization boundary

```text
Diarization is not implemented.
Speaker separation is not implemented.
Speaker attribution is roadmap only.
Use Unknown / Unassigned unless real speaker labels exist.
```

Forbidden claims:

```text
- production diarization exists
- real speaker separation exists
- Speaker_1 / Speaker_2 attribution is reliable
```

## Success condition

```text
A transcript can become structured memory without manual database fixing.
The user can ask questions and receive evidence-based answers with source references.
```
