# Collective MindGraph Roadmap

The current release establishes the single-package, single-data-owner product
architecture. Future work is ordered by evidence and user value rather than by
temporary release labels.

## Quality evidence

- Build human-reviewed Turkish meeting-room fixtures across noise, distance,
  overlap, and microphone conditions.
- Report WER/CER and domain-term accuracy only against those references.
- Validate optional Silero behavior on target Windows hardware.

## Retrieval quality

- Evaluate real local embedding models with labelled search judgments.
- Add explainable reranking when evidence shows a measurable benefit.
- Expand relationship extraction without weakening source traceability.

## Audio and speaker research

- Bound streaming backlog and upload size.
- Validate speaker separation before promoting it from Labs.
- Preserve channel information where it improves multi-speaker recordings.

## Distribution

- Complete clean-machine PyInstaller smoke tests.
- Add repeatable installer, signing, upgrade, backup, and rollback validation.
- Keep the canonical user-data path stable across upgrades.

Multi-user synchronization, cloud collaboration, a graph canvas, and dark theme
remain outside the current scope.
