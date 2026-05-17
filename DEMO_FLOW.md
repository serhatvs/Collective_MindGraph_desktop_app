# Local Demo Script

Follow these steps to demonstrate the end-to-end Collective MindGraph technical Turkish transcription and memory retrieval loop.

## Step 1: Environment Readiness
Run the health check to ensure local dependencies (ffmpeg, Faster-Whisper) are correctly configured.
```bash
./scripts/check_demo_readiness.sh
```

## Step 2: Seed Demo Data
Populate the system with a synthetic technical meeting session. This writes directly to the local storage, bypasses the need for immediate audio input, and runs the full heuristic extraction pipeline.
```bash
PYTHONPATH=. python realtime_backend/scripts/seed_demo_session.py
```

## Step 3: Start the Backend
Open a terminal and start the transcription service. It will default to CPU/int8/Turkish for maximum local compatibility.
```bash
./scripts/dev_backend.sh
```

## Step 4: Start the Desktop App
Open another terminal and launch the UI.
```bash
./scripts/dev_desktop.sh
```

## Step 5: Guided UI Walkthrough

### 1. View Seeded Session
- In the **Session Explorer** (left panel), find and select: `demo_technical_turkish`.
- View the **Cleaned Transcript** in the main area.
- Scroll down to see the **Extracted Tasks, Decisions, and Topics** (e.g., *FastAPI endpoint*, *SQLite storage*).
- Switch to the **Analysis** tab to compare the **Raw Text** vs. **Corrected Text**.

### 2. Global Memory Search
- Click the **"Global Search"** button in the left panel.
- Enter query: `FastAPI endpoint`
- Verify the task from the seeded session appears with a high score.
- Enter query: `raw transcript`
- Verify the decision about transcript separation appears.

### 3. Traceability Navigation
- **Double-click** any search result in the list.
- Observe the app automatically navigating back to the **Session Detail**.
- Observe the **segment table scrolling and highlighting** the exact source of that information.

---
**Status**: Local MVP Demo Ready. 
*Note: This flow demonstrates architectural integration and Turkish heuristic accuracy. Actual meeting-room audio performance is pending manual fixture validation.*
