$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

$env:PYTHONPATH = "src;."

$PreferredPython = Join-Path $RepoRoot ".venv-win\Scripts\python.exe"

if (Test-Path $PreferredPython) {
    $PythonExe = $PreferredPython
} else {
    $PythonExe = "python"
}

Write-Host "Starting Collective MindGraph desktop..."
Write-Host "Repo root: $RepoRoot"
Write-Host "Python: $PythonExe"

& $PythonExe -m collective_mindgraph_desktop
