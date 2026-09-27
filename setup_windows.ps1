# Launched only from a user click on the local Windows dashboard.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program exited with code $LASTEXITCODE" }
}

function Install-Package([string]$Id) {
    Write-Output "Installing/checking $Id with WinGet..."
    Invoke-Checked 'winget.exe' @('install', '--id', $Id, '--exact', '--source', 'winget',
        '--silent', '--no-upgrade', '--accept-package-agreements', '--accept-source-agreements')
}

function Get-Python311 {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        & $py.Source -3.11 -c 'import sys; assert sys.version_info[:2] == (3, 11)'
        if ($LASTEXITCODE -eq 0) { return @($py.Source, '-3.11') }
    }
    $localPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
    if (Test-Path $localPython) { return @($localPython) }
    return @()
}

Write-Output 'Motion Studio Windows setup: Python 3.11, Manim, FFmpeg, Ollama, a small planning model, and ComfyUI Desktop.'
if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
    throw 'WinGet is missing. Install Microsoft App Installer, then retry Windows setup.'
}
$python = @(Get-Python311)
if ($python.Count -eq 0) {
    Install-Package 'Python.Python.3.11'
    $python = @(Get-Python311)
    if ($python.Count -eq 0) { throw 'Python 3.11 was installed, but is not discoverable yet. Restart Motion Studio and retry.' }
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Output 'Creating the private Python environment...'
    $venvArgs = @()
    if ($python.Count -gt 1) { $venvArgs += $python[1..($python.Count - 1)] }
    $venvArgs += @('-m', 'venv', '.venv')
    Invoke-Checked $python[0] $venvArgs
}
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
Write-Output 'Installing Manim 0.19 in the private environment...'
Invoke-Checked $venvPython @('-m', 'pip', 'install', '--upgrade', 'pip', 'wheel')
Invoke-Checked $venvPython @('-m', 'pip', 'install', '-r', 'requirements.txt')
Invoke-Checked $venvPython @('-m', 'manim', '--version')

Install-Package 'Gyan.FFmpeg'
Install-Package 'Ollama.Ollama'
Install-Package 'Comfy.ComfyUI-Desktop'

$ollama = Get-Command ollama.exe -ErrorAction SilentlyContinue
if ($ollama) { $ollamaExe = $ollama.Source }
else { $ollamaExe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe' }
if (-not (Test-Path $ollamaExe)) { throw 'Ollama was installed but its executable is not available. Restart Motion Studio and retry.' }
try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 }
catch {
    Write-Output 'Starting the local Ollama service...'
    Start-Process -FilePath $ollamaExe
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 1
        try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2; $ready = $true; break }
        catch { }
    }
    if (-not $ready) { throw 'Ollama did not start. Open Ollama from the Start menu and retry setup.' }
}
Write-Output 'Downloading the local qwen2.5-coder:3b planning model (first run only)...'
Invoke-Checked $ollamaExe @('pull', 'qwen2.5-coder:3b')
Write-Output 'Windows essentials are ready. For abstract video, open ComfyUI Desktop, finish its NVIDIA setup, install an 8 GB VRAM-friendly video model, and export a working API workflow.'
