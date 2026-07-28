# Demo Questions and Answers

## Does it send meetings to the cloud?

Not by default. The engine runs on localhost, persistence is local, and remote
model endpoints/downloads are blocked unless explicitly allowed by a
local-safe configuration.

## Is speaker separation validated?

No. It remains an experimental Labs option. The product does not claim reliable
speaker identity or meeting-room diarization.

## Is the displayed confidence an accuracy score?

No. Confidence and audio-quality values are diagnostics. WER/CER is reported
only when a human reference transcript is supplied.

## What happens when a transcript is corrected?

Raw ASR text is preserved. Corrected text is stored separately and related
insights/knowledge items are marked for renewed review rather than deleted.

## Can rejected information answer a memory question?

Rejected content is excluded from normal search and answers. Pending content is
also excluded unless the caller explicitly asks to include it.

## Is a local language model required?

No. Evidence-only answers and deterministic extraction remain available. Local
embeddings and language-model enrichment are optional adapters.

## Where is data stored?

The canonical database is
`%LOCALAPPDATA%\CollectiveMindGraph\collective_mindgraph.sqlite3`. First-run
migration backs up legacy data and does not delete the original sources.

## Is there a visual graph canvas?

No. Knowledge is explored through filterable nodes, relationships, and evidence
details so the interface remains auditable and usable.
