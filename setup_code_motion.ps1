$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$scriptPath = Join-Path $PSScriptRoot 'code_motion_setup.py'
if (Test-Path $pythonPath) { & $pythonPath $scriptPath }
elseif (Get-Command python.exe -ErrorAction SilentlyContinue) { & python.exe $scriptPath }
elseif (Get-Command py.exe -ErrorAction SilentlyContinue) { & py.exe -3.11 $scriptPath }
else { throw 'Python 3.11 was not found. Launch start_windows.bat once, then retry.' }
exit $LASTEXITCODE
