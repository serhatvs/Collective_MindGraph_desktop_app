# Collective MindGraph — Friend Alpha Test Guide

> **Version**: Alpha · **Date**: July 2026  
> **Contact**: Share feedback directly with Serhat or open a GitHub issue using the bug report template.

---

## What is Collective MindGraph?

Collective MindGraph is a **local-first, privacy-focused desktop app** for Windows that helps you:

- Transcribe audio recordings of meetings, calls, or voice notes — **entirely on your own machine**
- Automatically extract tasks, decisions, and topics from the transcript
- Ask simple questions about what was discussed, backed by real evidence from the transcript
- Export the full session for your own records

There is **no cloud, no accounts, no data leaving your computer**.

---

## What You Should Try (Test Flow)

Follow these steps in order. Each one is a checkpoint.

### Step 1 — Launch the App

```powershell
# From the repo root
python scripts/launch_cmg.py
```

Or on Windows, double-click `scripts/launch_cmg.bat`.

**Expected**: The main window opens with a session explorer sidebar on the left.

---

### Step 2 — Transcribe a Local Audio File

1. In the sidebar, click **"Transcribe File"** (or use the main menu).
2. Select an audio file from your computer.

**Supported formats**:
| Format | Notes |
|--------|-------|
| `.wav` | Best quality, recommended |
| `.mp3` | Common, works well |
| `.flac` | Lossless, good quality |
| `.m4a` | iPhone recordings |

3. Wait for transcription to complete. Progress is shown in the status bar.
4. When done, the app will switch to the **Transcript** tab automatically.

**Expected**: You see your transcript text broken into segments with timestamps.

> **Tip**: For best results, use a recording with clear speech and minimal background noise.  
> Audio longer than ~30 minutes may take several minutes to transcribe on CPU.

---

### Step 3 — View the Transcript

After transcription, open the **Transcript** tab if it is not already visible.

- Segments are shown in order with timestamps
- Scroll through to confirm the text looks correct
- If the transcript is empty or shows placeholder text, see [Known Limitations](#known-limitations)

---

### Step 4 — Check Extracted Notes

Open the **Knowledge Audit** tab (may also appear as **Extracted Notes** or **Insights**).

You should see items extracted from the transcript, grouped by type:

| Type | What it means |
|------|--------------|
| **Tasks** | Action items mentioned in the recording |
| **Decisions** | Conclusions or choices made |
| **Topics** | Main subjects discussed |

- Items marked **Pending Review** have not been approved yet
- Click **Approve** to add an item to your memory graph
- Click **Reject** to dismiss it

**Expected**: At least some extracted items appear if the transcript contains structured speech.

---

### Step 5 — Ask a Simple Question

Open the **Ask Memory** tab.

1. Make sure the session you just transcribed is selected in the sidebar
2. Type a simple question based on what was discussed, e.g.:
   - *"What tasks were assigned?"*
   - *"What was decided about X?"*
   - *"Who should follow up?"*
3. Press **Ask** (or Enter)

**Expected**: An answer appears with **evidence** — quoted text from the transcript that supports the answer.

> **Note**: If no local LLM is running, Ask Memory will use evidence from the transcript directly without LLM-generated summaries. This is expected behavior, not a crash.

---

### Step 6 — Export the Session

1. Select the session in the sidebar
2. Click **Export** (sidebar button or menu)
3. Choose a save location

**Expected**: A `.json` file is saved containing the transcript, extracted notes, and memory graph for that session.

---

## What Feedback to Give

Please note the following for each test run:

- ✅ / ❌ Did each step above work?
- Was the transcript readable and accurate?
- Did the extracted notes make sense?
- Did Ask Memory give a relevant answer?
- Did the export file save correctly?
- Any crashes, freezes, or confusing UI?
- How long did transcription take?
- What was your audio format, length, and language?

Use the **[Bug Report Template](../../.github/ISSUE_TEMPLATE/alpha_bug_report.md)** on GitHub for any issues.

---

## Known Limitations

This is an early alpha. Please read before testing:

| Limitation | Detail |
|------------|--------|
| **No speaker separation** | All speech is treated as one speaker. Diarization is on the roadmap. |
| **No diarization** | You cannot identify who said what. |
| **LLM is optional** | Ask Memory and extraction work without a local LLM, but answers are less fluent. |
| **Transcription quality** | Depends heavily on audio quality, background noise, and microphone. |
| **Turkish-first** | The app was designed and tested primarily with Turkish speech. Other languages may work but are not validated. |
| **No cloud** | Everything runs locally. Cold-start transcription of large files on CPU can be slow. |
| **Alpha UI** | Some screens may have rough edges, unclear labels, or missing error states. |
| **Crashes possible** | This is alpha software. Please report crashes with steps to reproduce. |
| **No installer yet** | Launch requires Python and repo dependencies installed manually. |

---

## Requirements

- Windows 10 or 11
- Python 3.11+ installed and on PATH
- Repo dependencies installed: `pip install -r requirements.txt` (or equivalent)
- ~4 GB free disk space for local ASR models (downloaded on first run)

---

## Quick Reference

```text
Launch:         python scripts/launch_cmg.py
Transcribe:     Sidebar → Transcribe File → select audio
View:           Transcript tab
Extract:        Knowledge Audit / Insights tab
Ask:            Ask Memory tab → type question → Ask
Export:         Sidebar → Export (select session first)
```

---

*Thank you for testing Collective MindGraph. Your feedback directly shapes the first real release.*
