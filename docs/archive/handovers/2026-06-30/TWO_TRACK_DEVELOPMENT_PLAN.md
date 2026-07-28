# Collective MindGraph - Two-Track Development Plan

## 1. Purpose of the split

Collective MindGraph now has two distinct engineering tracks:

- Transcription is the foundation.
- Memory is the product.
- The split prevents scope pollution between ASR validation and product memory work.
- The transcription branch must not touch memory features.
- The memory branch must not touch ASR or audio behavior.

## 2. Branches

```text
feature/transcription-quality-pipeline
feature/transcript-to-memory-pipeline
```

## 3. Recommended worktrees

```text
../cmg-transcription
../cmg-memory
```

## 4. Transcription Track Scope

Allowed:

- ASR / STT pipeline
- Faster-Whisper settings
- Turkish language defaults
- Turkish character preservation
- raw_transcript / cleaned_transcript separation
- transcript cleanup
- transcription benchmark scripts
- transcription setup docs
- transcription bugfixes
- audio preprocessing only if a real transcription bug requires it

Forbidden:

- memory graph
- Ask Memory
- human review lifecycle
- graph reasoning
- visual graph UI
- hardware/device code
- patent wording
- diarization
- speaker separation
- unrelated refactors

Goal:

Freeze current transcription baseline, validate it, document safe claims, and provide stable transcript output for the memory branch.

## 5. Memory Track Scope

Allowed:

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

Forbidden:

- ASR quality tuning
- audio preprocessing
- ffmpeg normalization
- Faster-Whisper model settings
- VAD tuning
- diarization
- speaker separation
- transcription benchmark logic

Goal:

Prove that Collective MindGraph can turn Turkish transcripts into trusted, reviewable, source-linked organizational memory.

## 6. Shared Transcript Contract

Both tracks must agree on this transcript output shape:

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

Segment shape:

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

- Transcription branch produces this contract.
- Memory branch consumes this contract.
- Memory branch must not care how ASR produced the transcript.
- Transcription branch must not care how memory extraction uses it.

## 7. Diarization Boundary

- Diarization is not implemented.
- Speaker separation is not implemented.
- Speaker attribution is roadmap only.
- Use Unknown / Unassigned unless real speaker labels exist.

Forbidden claims:

- Speaker_1 / Speaker_2 production attribution exists.
- production diarization exists.
- real speaker separation exists.

## 8. Merge / Sync Rules

Transcription to Memory:

Only merge when:

- transcript output contract changes
- transcription bugfix affects memory input
- benchmark/docs clarify safe transcript assumptions

Memory to Transcription:

Avoid unless absolutely necessary.

Main branch:

Only merge when:

- scope is respected
- tests pass
- no forbidden areas were modified
- safe claims are documented
