@echo off
setlocal
REM install_friend_alpha_deps.bat - Collective MindGraph friend alpha setup.
REM Double-click this file or run it from any working directory before launching the app.

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

echo.
echo  Collective MindGraph - Friend Alpha Setup
echo  -----------------------------------------
echo.

if not exist "%REPO_ROOT%\pyproject.toml" (
    echo  [CMG] Setup failed: repository root could not be resolved.
    echo  Expected to find:
    echo    %REPO_ROOT%\pyproject.toml
    echo.
    echo  Press any key to close this window...
    pause >nul
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo  [CMG] Setup failed: Python was not found on PATH.
    echo  Install Python 3.11+ or open a terminal where Python is available.
    echo.
    echo  Press any key to close this window...
    pause >nul
    exit /b 1
)

pushd "%REPO_ROOT%" >nul
python "%SCRIPT_DIR%install_friend_alpha_deps.py"
set "CMG_EXIT=%ERRORLEVEL%"
popd >nul

if not "%CMG_EXIT%"=="0" (
    echo.
    echo  [CMG] Setup failed. See output above.
    echo  Press any key to close this window...
    pause >nul
    exit /b %CMG_EXIT%
)

echo.
echo  [CMG] Setup complete. You can now run scripts\launch_cmg.bat.
exit /b 0
