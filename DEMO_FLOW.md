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
**Status**: The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.

## Troubleshooting: Desktop App Window Not Appearing
The **native PySide6 desktop app** is the only user-facing frontend. If the window does not appear after running `./scripts/dev_desktop.sh`:

1.  **Check Display Environment**:
    ```bash
    echo "DISPLAY=$DISPLAY"
    echo "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
    ```
    Ensure you are in a graphical environment (X11 or Wayland).

2.  **Verify Process**:
    ```bash
    pgrep -af python | grep collective_mindgraph_desktop
    ```

3.  **Debug Qt Plugins**:
    If there are platform errors, run with plugin debugging:
    ```bash
    QT_DEBUG_PLUGINS=1 ./scripts/dev_desktop.sh
    ```

4.  **Virtual Environment**:
    The desktop app requires PySide6, which is installed in `realtime_backend/.venv`. The `dev_desktop.sh` script handles this automatically if the venv exists.

*Note: The backend API at `127.0.0.1:8081` is a background service and is not the intended user interface. Use `/docs` only for developer debugging.*

*Note: This flow demonstrates architectural integration and Turkish heuristic accuracy. Actual meeting-room audio performance is pending manual fixture validation.*
