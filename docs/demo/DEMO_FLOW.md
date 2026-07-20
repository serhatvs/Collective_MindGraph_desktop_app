# Local Demo Script

Follow these steps to demonstrate the end-to-end Collective MindGraph technical Turkish transcription and memory retrieval loop.

## Step 1: Environment Readiness
Run the health check to ensure local dependencies (ffmpeg, Faster-Whisper) are correctly configured.
```bash
./scripts/setup/check_demo_readiness.sh
```

## Step 2: Seed Demo Data
Populate the system with a synthetic technical meeting session. This writes directly to the local storage, bypasses the need for immediate audio input, and runs the full heuristic extraction pipeline.
```bash
PYTHONPATH=. python realtime_backend/scripts/seed_demo_session.py
```

## Step 3: Start the Backend
Open a terminal and start the transcription service. It will default to CPU/int8/Turkish for maximum local compatibility.
```bash
./scripts/launch/dev_backend.sh
```

## Step 4: Start the Desktop App
Open another terminal and launch the UI.
```bash
./scripts/launch/dev_desktop.sh
```

## Step 5: Guided UI Walkthrough

### 1. Explore the Rebuilt MVP UI
Observe the modern 3-area layout:
- **Left Sidebar**: The Session Explorer and primary actions.
- **Main Content**: Tabbed interface (Overview, Transcript, Insights, Memory Search).
- **Voice Ingest**: header for real-time capture.

1.  **Select 'demo_technical_turkish'** in the sidebar.
2.  **View Overview**: See high-level intelligence metrics (Task/Decision counts).
3.  **Click 'Transcript' Tab**: Observe the side-by-side comparison.
    -   **Cleaned Transcript**: Main readable view with technical corrections.
    -   **Raw Text**: Original ASR output (in gray) for auditability.
4.  **Click 'Insights' Tab**: See extracted **Tasks** and **Decisions**.

### 2. Global Memory Search
1.  **Click 'Memory Search' Tab** (or 'Global Memory Search' button in sidebar).
2.  **Enter Search**: Type `FastAPI endpoint`.
3.  **Inspect Results**: Note the **Result Cards** with type badges (TASK, TOPIC, etc.).
4.  **Traceability**: **Double-click** a result.
5.  **Navigation**: Observe the app automatically switching to the **Transcript Tab** and highlighting the exact source segment.

---
**Status**: The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It does not currently include validated diarization or production meeting-room speaker separation.

## Troubleshooting: Desktop App Window Not Appearing
The **native PySide6 desktop app** is the only user-facing frontend. If the window does not appear after running `./scripts/launch/dev_desktop.sh`:

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
    QT_DEBUG_PLUGINS=1 ./scripts/launch/dev_desktop.sh
    ```

4.  **Confirm New UI**:
    The new UI window title is: **"Collective MindGraph — Native MVP UI"**.
    The status bar (bottom right) contains: **"Collective MindGraph Desktop — New MVP UI"**.
    If you see a different title, you are running an old version. Clear `__pycache__` and ensure `PYTHONPATH` is correct.

5.  **Virtual Environment**:
    The desktop app requires PySide6. The `dev_desktop.sh` script handles this if `realtime_backend/.venv` exists.

*Note: The backend API at `127.0.0.1:8080` is a background service and is not the intended user interface. Use `/docs` only for developer debugging.*

*Note: This flow demonstrates architectural integration and Turkish heuristic accuracy. Actual meeting-room audio performance is pending manual fixture validation.*
