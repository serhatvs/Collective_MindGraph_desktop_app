@echo off
REM launch_cmg.bat — Collective MindGraph Windows launcher
REM Double-click this file (or run from repo root) to start the app.

echo.
echo  Collective MindGraph ^— Alpha Launcher
echo  ----------------------------------------
echo.

python scripts\launch_cmg.py
if errorlevel 1 (
    echo.
    echo  [CMG] Launch failed. See output above.
    echo  Press any key to close this window...
    pause >nul
)
