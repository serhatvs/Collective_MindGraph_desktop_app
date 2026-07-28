# Friend Test Guide

This guide is for a local Windows test of the current six-workspace desktop.
Use non-sensitive sample audio and report what you actually observe.

## Before starting

1. Install the application or follow `docs/dev/SETUP.md`.
2. Make sure FFmpeg is available.
3. Use headphones if the sample contains confidential speech.
4. Do not enable speaker separation unless you are intentionally testing the
   experimental Labs control.

The desktop starts its localhost engine automatically. There is one engine and
one canonical database; no second service or desktop database needs to be
started.

## Test flow

### 1. Start and language

1. Open Collective MindGraph.
2. Confirm the left navigation contains Home, Capture, Meetings, Memory,
   Knowledge, and Settings.
3. Open Settings and switch between Turkish and English.
4. Confirm the visible workspace updates without restarting.

Expected: the engine indicator becomes ready or honestly reports a degraded,
disabled, or unavailable optional adapter. Missing local models must not be
shown as ready.

### 2. Add an audio file

1. From Home, use the file action; it should open the picker directly.
2. Select a short WAV, MP3, FLAC, M4A, OGG, OPUS, AAC, or WMA sample.
3. Watch the job progress through preparation, normalization, speech
   detection, transcription, alignment, extraction, and persistence.

Expected: upload returns immediately to the interface and processing continues
as a background job. You can leave the workspace without losing the job.

### 3. Test cancel and retry

1. Start a long-enough file job.
2. Cancel it while it is running.
3. Use Retry on the failed/cancelled operation.

Expected: cancellation stops the actual task. The source audio remains
available for retry and the retry appears as a new, related job.

### 4. Test live capture

1. In Settings, choose a microphone.
2. Open Capture and start live recording.
3. Speak a few sentences and watch partial text/progress.
4. Stop and start a second recording.

Expected: the selected device is used, stopping produces one final ingest, and
another recording can start immediately. If the WebSocket finalization fails,
the locally spooled recording is uploaded automatically.

### 5. Review a meeting

1. Open Meetings and select the new meeting.
2. Check Overview, Transcript, Insights, and Evidence.
3. Correct one transcript segment.
4. Edit an insight title/body, then accept or reject it.

Expected: raw text remains unchanged, corrected text is stored separately, and
derived accepted content becomes `needs review` instead of being deleted.
Evidence displays readable text, timestamps, and its source meeting.

### 6. Ask memory

1. Open Memory.
2. Search for a phrase that appears in the transcript.
3. Ask a question whose answer is present in the evidence.

Expected: the answer shows sources, evidence previews, timestamps, reasoning
steps, warnings, and sentence validation. Rejected, pending, and `needs review`
insights are excluded by default. Verified transcript segments remain
searchable.

If embeddings are disabled, hybrid mode should fall back to keyword/graph
search with a warning. Semantic-only mode should report that the provider is
unavailable; it must not return fake semantic matches.

### 7. Explore knowledge

1. Open Knowledge.
2. Filter nodes and relationships by type, meeting, review state, and text.
3. Select an item.

Expected: the detail panel shows readable relationships and evidence. A graph
canvas is intentionally not part of this release.

### 8. Privacy and export

1. In Settings, review Privacy/Storage.
2. Confirm “keep raw audio” is off unless you explicitly need it.
3. Export data and inspect the resulting JSON.

Expected: successful job audio is removed by default; failed/cancelled audio is
retained for retry. Export declares `format_version: 4`.

## What to report

Include:

- Windows version and app build/commit;
- language and selected audio device;
- exact workspace and action;
- expected versus observed behavior;
- job ID or meeting title when relevant;
- screenshot of the visible error;
- whether Retry recovered the operation.

Do not attach private meeting audio, databases, model files, access tokens, or
machine-specific secrets.
