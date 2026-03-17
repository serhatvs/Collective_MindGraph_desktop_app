param(
    [string]$PythonExe = "",
    [switch]$SkipBootstrap
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $venvPython = Join-Path $repoRoot "realtime_backend\.venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonExe = $venvPython
    } else {
        $PythonExe = "python"
    }
}

Write-Host "Using Python:" $PythonExe

if (-not $SkipBootstrap) {
    & $PythonExe -m pip install -e .
    & $PythonExe -m pip install "PyInstaller>=6.12,<7.0"
}

& $PythonExe -m PyInstaller --noconfirm --clean .\CollectiveMindGraph.spec

Write-Host ""
Write-Host "Build complete:"
Write-Host "  dist\CollectiveMindGraph.exe"
