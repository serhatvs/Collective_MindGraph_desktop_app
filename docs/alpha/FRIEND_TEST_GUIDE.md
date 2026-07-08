# Collective MindGraph - Friend Alpha Test Guide

Version: Alpha
Date: July 2026
Contact: Share feedback directly with Serhat or open a GitHub issue using the bug report template.

## What This Alpha Is

Collective MindGraph is a local-first Windows desktop app for testing a basic meeting-memory flow:

1. Open the desktop app.
2. Select a local audio file.
3. Transcribe it locally, Turkish-first.
4. Review the transcript in the UI.
5. Review extracted tasks, decisions, and topics.
6. Ask a simple question about the selected session.
7. Export the session result.

There are no accounts and no cloud transcription APIs in this alpha.

## Before Giving This To Testers

Run this developer preflight first:

```powershell
python scripts/launch_cmg.py
```

Confirm all of these before handing the app to friends:

- The desktop app opens.
- The local backend starts automatically.
- `faster_whisper` is reported as `available` by the launcher.
- Diagnostics or backend health shows `ASR_STATUS=OK`, not `ASR_STATUS=MOCK_FALLBACK`.
- One real Turkish audio file transcribes into real Turkish text, not placeholder text.
- The transcript appears in `Knowledge Audit`.
- Extracted notes appear in `Extracted Notes`, or a clear empty state appears.
- A simple selected-session question works from the Ask Memory panel in `Global Search`.
- `Export Selected Session` writes a JSON file.

### Mock Fallback Means Transcription Is Not Real

If the launcher prints:

```text
Real transcription is not available. The app may use mock fallback.
```

or backend health shows:

```text
ASR_STATUS=MOCK_FALLBACK
```

then Faster-Whisper is missing or could not load. The app may still open and the flow may still create a placeholder transcript, but that is not real transcription and is not ready for friend testing.

The backend dependency install path for real ASR is:

```powershell
python -m pip install -r realtime_backend\requirements.txt
```

For GPU setups, follow `realtime_backend/README.md` first, because PyTorch/CUDA installs may need a specific command before installing backend requirements.

## Launch The App

From the repo root:

```powershell
python scripts/launch_cmg.py
```

On Windows you can also double-click:

```text
scripts\launch_cmg.bat
```

Expected: the main window opens with a session explorer sidebar on the left.

## Transcribe A Local Audio File

1. In the sidebar, click `Transcribe Local File`.
2. Select an audio file from your computer.

Supported formats:

| Format | Notes |
| --- | --- |
| `.wav` | Best quality, recommended |
| `.mp3` | Common compressed format |
| `.flac` | Lossless audio |
| `.m4a` | Common phone recording format |

Expected: the status bar shows transcription progress. When transcription finishes, the app switches to `Knowledge Audit`.

## View The Transcript

Open the `Knowledge Audit` tab.

Expected:

- Transcript rows are visible.
- Timestamp, speaker, corrected transcript, and raw ASR output columns are shown when segment details are available.
- Turkish text is readable.
- Placeholder text containing `ASR_STATUS=MOCK_FALLBACK` means transcription was not real.

## Check Extracted Notes

Open the `Extracted Notes` tab.

Expected:

- Tasks, decisions, topics, and other extracted items appear if the transcript contains enough structure.
- New items may show `[pending review]`.
- If nothing was extracted, the empty state should explain what to do next.

## Ask A Simple Question

Open the `Global Search` tab. The Ask Memory panel is at the top.

1. Make sure the transcribed session is selected in the sidebar.
2. Ask a simple question grounded in the session, such as:
   - `What tasks were assigned?`
   - `What was decided?`
   - `What topics did we discuss?`
3. Click `Ask` or press Enter.

Expected:

- The app answers from available session evidence when possible.
- Evidence/source details appear below the answer.
- If there is no evidence, the app says so clearly.
- A local LLM is optional; lack of LLM is not a crash.

## Export The Session

1. Select the session in the sidebar.
2. Click `Export Selected Session`.
3. Choose a save location.

Expected: a `.json` file is saved containing the transcript, extracted notes, and memory graph data for the selected session.

## What To Report

Please include:

- What you tried.
- What you expected.
- What actually happened.
- Whether the app crashed, froze, or stayed open.
- Audio format and approximate length.
- Whether the transcript was real text or mock fallback placeholder text.
- Screenshot or terminal output if available.

Use `.github/ISSUE_TEMPLATE/alpha_bug_report.md` for structured bug reports.

## Known Limitations

| Limitation | Detail |
| --- | --- |
| No diarization | The app does not identify who said what. |
| No speaker separation | All speech may appear as unknown or generic speaker labels. |
| LLM optional | Ask Memory and extraction should still have evidence-only behavior without a local LLM. |
| Transcription quality varies | Results depend on audio quality, noise, microphone, and local ASR setup. |
| Turkish-first | Turkish is the primary alpha target. Other languages are not validated. |
| No installer yet | Launch currently requires Python and repo dependencies installed manually. |
| Alpha UI | Some screens may still have rough labels or empty states. |

## Quick Reference

```text
Launch:      python scripts/launch_cmg.py
Transcribe:  Sidebar -> Transcribe Local File -> select audio
Transcript:  Knowledge Audit
Notes:       Extracted Notes
Ask:         Global Search -> Ask Memory panel -> Ask
Export:      Sidebar -> Export Selected Session
```

Thank you for testing Collective MindGraph. Your feedback directly shapes the first real release.
