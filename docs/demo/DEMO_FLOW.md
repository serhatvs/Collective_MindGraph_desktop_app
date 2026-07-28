# Collective MindGraph Demo Flow

## Preparation

```powershell
python -m pip install -e ".[transcription,local-ai]"
mindgraph
```

The desktop normally starts the localhost engine automatically. For a
split-process demonstration, start `mindgraph-engine` first.

Optional deterministic sample data:

```powershell
python scripts/datasets/seed_demo_meeting.py
```

## Walkthrough

1. **Home**
   - Show recent meetings, pending reviews, and the compact engine status.
   - Point out quick capture, file ingest, and the short memory-question field.

2. **Capture**
   - Add a local WAV/MP3 file or begin a live recording.
   - Keep advanced ASR controls collapsed unless the audience asks.
   - Explain that processing stays local and that confidence is not claimed as
     measured accuracy.

3. **Meetings**
   - Open the new meeting.
   - Compare immutable raw text with corrected text.
   - Correct one segment and show that linked insights are marked for renewed
     review rather than deleted.

4. **Knowledge**
   - Accept one insight and reject another.
   - Filter nodes by type or review state.
   - Select a node to show relationships and evidence without a graph canvas.

5. **Memory**
   - Search for a term from the accepted insight.
   - Ask a question and show the answer, source identifiers, and reasoning
     trace.
   - Confirm that rejected content is excluded by default.

6. **Settings**
   - Switch Turkish/English without restarting.
   - Show privacy/diagnostics and the clearly labelled Labs controls.

## Claim boundary

Demonstrate the verified local workflow. Do not claim validated speaker
separation, general meeting-room accuracy, semantic retrieval without a real
local embedding model, or a certified installer.
