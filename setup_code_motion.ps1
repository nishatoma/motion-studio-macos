$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program exited with code $LASTEXITCODE" }
}
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js 22 LTS or newer, then restart this terminal.'
}
Invoke-Checked 'node.exe' @('-e', 'if (Number(process.versions.node.split(".")[0]) < 22) throw Error("Node.js 22 or newer required")')
if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
    throw 'Install/start Docker Desktop with WSL2 Linux containers, then retry.'
}
Invoke-Checked 'docker.exe' @('info')
Invoke-Checked 'npm.cmd' @('ci', '--prefix', 'code-motion')
Invoke-Checked 'npm.cmd' @('test', '--prefix', 'code-motion')
Invoke-Checked 'docker.exe' @('build', '-t', 'motion-studio-remotion:1', 'code-motion')
Write-Output 'Code Motion ready. Set OPENAI_API_KEY and OPENAI_MODEL on the backend, then restart Motion Studio.'
