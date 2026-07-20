@echo off
setlocal
REM launch_cmg.bat - Collective MindGraph Windows launcher
REM Double-click this file or run it from any working directory to start the app.

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%..\.."

echo.
echo  Collective MindGraph - Alpha Launcher
echo  ----------------------------------------
echo.

if not exist "%REPO_ROOT%\src" (
    echo  [CMG] Launch failed: repository root could not be resolved.
    echo  Expected to find:
    echo    %REPO_ROOT%\src
    echo.
    echo  Press any key to close this window...
    pause >nul
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo  [CMG] Launch failed: Python was not found on PATH.
    echo  Install Python 3.11+ or open a terminal where Python is available.
    echo.
    echo  Press any key to close this window...
    pause >nul
    exit /b 1
)

pushd "%REPO_ROOT%" >nul
python "%SCRIPT_DIR%launch_cmg.py"
set "CMG_EXIT=%ERRORLEVEL%"
popd >nul

if not "%CMG_EXIT%"=="0" (
    echo.
    echo  [CMG] Launch failed. See output above.
    echo  Press any key to close this window...
    pause >nul
    exit /b %CMG_EXIT%
)

exit /b 0
