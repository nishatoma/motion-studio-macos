# Native Windows PowerShell 5.1 + Python + Node/npm. Docker itself is simulated;
# the Linux workflow tests the real production renderer.
$ErrorActionPreference = 'Stop'
$fixtureRoot = Join-Path $env:RUNNER_TEMP ('Motion Studio With Spaces ' + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $fixtureRoot | Out-Null
$sourceRoot = Split-Path $PSScriptRoot -Parent
$previousPath = $env:Path
$previousDockerHost = $env:DOCKER_HOST
$env:MOCK_DOCKER_IMAGE = Join-Path $fixtureRoot 'image-ready'
$env:MOCK_DOCKER_LOG = Join-Path $fixtureRoot 'docker-calls.log'
$env:DOCKER_HOST = 'tcp://127.0.0.1:1'
$env:Path = $fixtureRoot + ';' + $env:Path
try {
    foreach ($name in @('code_motion_setup.py','render_runtime.py','windows_support.py','setup_code_motion.ps1')) {
        Copy-Item (Join-Path $sourceRoot $name) (Join-Path $fixtureRoot $name)
    }
    @'
def command():
    raise ValueError('Test fixture: dependencies not installed')
'@ | Set-Content -Encoding ASCII (Join-Path $fixtureRoot 'codex_provider.py')
    $engineRoot = Join-Path $fixtureRoot 'code-motion'
    New-Item -ItemType Directory -Path $engineRoot | Out-Null
    '{"name":"fixture-project","version":"1.0.0","scripts":{"test":"node native-test.js"}}' | Set-Content -Encoding ASCII (Join-Path $engineRoot 'package.json')
    '{"name":"fixture-project","version":"1.0.0","lockfileVersion":3,"requires":true,"packages":{"":{"name":"fixture-project","version":"1.0.0"}}}' | Set-Content -Encoding ASCII (Join-Path $engineRoot 'package-lock.json')
    'console.log("native npm test passed");' | Set-Content -Encoding ASCII (Join-Path $engineRoot 'native-test.js')
    $dockerSource = @'
using System;
using System.IO;
using System.Linq;
public class DockerFixture {
  public static int Main(string[] args) {
    File.AppendAllText(Environment.GetEnvironmentVariable("MOCK_DOCKER_LOG"),string.Join("|",args)+"\n");
    if(args.Contains("context") && args.Contains("inspect")) {
      Console.WriteLine("npipe:////./pipe/dockerDesktopLinuxEngine"); return 0;
    }
    if(!args.Contains("--context") || !args.Contains("desktop-linux") || !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("DOCKER_HOST"))) {
      Console.Error.WriteLine("Test: stale Docker connection"); return 3;
    }
    if(args.Contains("info")) { Console.WriteLine("linux");return 0; }
    if(args.Contains("image") && args.Contains("inspect")) {
      if(File.Exists(Environment.GetEnvironmentVariable("MOCK_DOCKER_IMAGE")))return 0;
      Console.Error.WriteLine("No such image: motion-studio-remotion:1");return 1;
    }
    if(args.Contains("build")) {
      Console.Error.WriteLine("normal native build progress on stderr");
      if(Environment.GetEnvironmentVariable("MOCK_BUILD_FAIL")=="1") { Console.Error.WriteLine("fixture build failure");return 17; }
      File.WriteAllText(Environment.GetEnvironmentVariable("MOCK_DOCKER_IMAGE"),"ready");return 0;
    }
    return 9;
  }
}
'@
    Add-Type -TypeDefinition $dockerSource -OutputAssembly (Join-Path $fixtureRoot 'docker.exe') -OutputType ConsoleApplication
    $output = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $fixtureRoot 'setup_code_motion.ps1')
    if ($LASTEXITCODE -ne 0) { throw ('Setup failed: ' + ($output -join "`n")) }
    $events = @($output | ForEach-Object { $_ | ConvertFrom-Json })
    if ($events[-1].stage -ne 'Ready') { throw 'Ready stage missing' }
    if (-not (($events | ForEach-Object { $_.log }) -join "`n").Contains('native npm test passed')) { throw 'Actual Node/npm test did not run' }
    if (-not (($events | ForEach-Object { $_.log }) -join "`n").Contains('normal native build progress')) { throw 'Native stderr was not captured as progress' }
    if (-not (Get-Content $env:MOCK_DOCKER_LOG -Raw).Contains('--context|desktop-linux|build')) { throw 'Build used the wrong Docker connection' }
    Remove-Item $env:MOCK_DOCKER_IMAGE
    $env:MOCK_BUILD_FAIL = '1'
    $output = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $fixtureRoot 'setup_code_motion.ps1')
    if ($LASTEXITCODE -ne 1) { throw 'Failed build did not return failure' }
    $errorEvent = $output[-1] | ConvertFrom-Json
    if (-not $errorEvent.message.Contains('exit 17') -or -not $errorEvent.message.Contains('fixture build failure')) { throw 'Exact failed stage/exit/log missing' }
    Write-Output 'PASS: Windows PowerShell 5.1 launcher, real Node/npm, spaced paths, stale Docker connection fallback, native stderr progress, explicit build failure. Docker CLI simulated.'
} finally {
    $env:Path = $previousPath
    Remove-Item -Recurse -Force $fixtureRoot
    Remove-Item Env:MOCK_DOCKER_IMAGE,Env:MOCK_DOCKER_LOG,Env:MOCK_BUILD_FAIL,Env:DOCKER_HOST -ErrorAction SilentlyContinue
    $env:DOCKER_HOST = $previousDockerHost
}
