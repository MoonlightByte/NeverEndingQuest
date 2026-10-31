# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
<#
.SYNOPSIS
  Build the desktop game server folder dist-server\neq-server with PyInstaller (#1681).

.DESCRIPTION
  From a clean checkout, in Windows PowerShell 5.1 or PowerShell 7:
    powershell -ExecutionPolicy Bypass -File desktop\pyinstaller\build.ps1 -Python C:\Path\To\Python312\python.exe

  Steps: engine pair check; a fresh venv from the hash-locked
  requirements-build.txt (pip --require-hashes); React player check (built if
  stale, which needs Node.js); tiktoken cl100k_base fetched and hash-checked;
  PyInstaller with neq-server.spec; the engine copies in the output checked
  against bin\; a smoke test of the built server unless -SkipSmoke.
  Output: dist-server\neq-server\run_web.exe (files in dist-server\neq-server\_internal).
  0 model calls: the smoke test never sends a model request.
#>
param(
    [string]$Python = "python",
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3.0

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root
$Work = Join-Path $Root "build-server"
$Out = Join-Path $Root "dist-server\neq-server"

function Step($text) { Write-Host "[BUILD] $text" }
function Fail($text) { Write-Host "[FAIL] $text"; exit 1 }
function Sha256($path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant() }

# 1. Engine pair check: both names present, byte-identical, version files set.
Step "Engine pair check"
$engine = Join-Path $Root "bin\firelight-apply.exe"
$twin = Join-Path $Root "bin\nql-apply.exe"
foreach ($f in @($engine, $twin, "bin\FIRELIGHT_ENGINE_VERSION.txt", "bin\NQL_ENGINE_VERSION.txt")) {
    if (-not (Test-Path -LiteralPath $f)) { Fail "missing $f" }
}
$engineHash = Sha256 $engine
if ($engineHash -ne (Sha256 $twin)) { Fail "bin\firelight-apply.exe and bin\nql-apply.exe differ" }
$fireVer = (Get-Content "bin\FIRELIGHT_ENGINE_VERSION.txt" -Raw).Trim()
$nqlVer = (Get-Content "bin\NQL_ENGINE_VERSION.txt" -Raw).Trim()
if (-not $fireVer -or -not $nqlVer) { Fail "an engine version file is empty" }
Step "  engine $fireVer ($nqlVer), sha256 $engineHash"

# 2. Python 3.12, 64-bit.
$check = & $Python -c "import struct, sys; print(sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8)"
if ($LASTEXITCODE -ne 0 -or $check -ne "True") { Fail "$Python is not a 64-bit Python 3.12" }

# 3. Fresh build venv from the hash-locked requirements.
Step "Build venv (pip --require-hashes)"
foreach ($d in @($Work, $Out)) { if (Test-Path -LiteralPath $d) { Remove-Item -Recurse -Force -LiteralPath $d } }
New-Item -ItemType Directory -Force -Path $Work | Out-Null
& $Python -m venv (Join-Path $Work "venv")
if ($LASTEXITCODE -ne 0) { Fail "venv creation failed" }
$VPy = Join-Path $Work "venv\Scripts\python.exe"
& $VPy -m pip install --disable-pip-version-check --require-hashes -r "desktop\pyinstaller\requirements-build.txt"
if ($LASTEXITCODE -ne 0) { Fail "pip install --require-hashes failed" }

# 4. React player: current, or built now.
Step "React player"
& $VPy run_web.py --frontend-ready
if ($LASTEXITCODE -ne 0) {
    & $VPy run_web.py --prepare-frontend
    if ($LASTEXITCODE -ne 0) { Fail "web/frontend/dist could not be built (Node.js needed)" }
}

# 5. tiktoken cl100k_base, stored under the name tiktoken looks for.
Step "tiktoken cl100k_base"
$tkUrl = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
$tkHash = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"
$sha1 = [System.Security.Cryptography.SHA1]::Create()
$tkKey = -join ($sha1.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($tkUrl)) | ForEach-Object { $_.ToString("x2") })
$tkDir = Join-Path $Work "tiktoken_cache"
New-Item -ItemType Directory -Force -Path $tkDir | Out-Null
$tkFile = Join-Path $tkDir $tkKey
Invoke-WebRequest -UseBasicParsing -Uri $tkUrl -OutFile $tkFile
if ((Sha256 $tkFile) -ne $tkHash) { Fail "cl100k_base.tiktoken hash mismatch" }

# 6. PyInstaller.
Step "PyInstaller"
$env:NEQ_TIKTOKEN_CACHE = $tkDir
& $VPy -m PyInstaller --noconfirm --clean --distpath (Join-Path $Root "dist-server") --workpath (Join-Path $Work "work") "desktop\pyinstaller\neq-server.spec"
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller failed" }
$Exe = Join-Path $Out "run_web.exe"
$Internal = Join-Path $Out "_internal"
if (-not (Test-Path -LiteralPath $Exe)) { Fail "missing $Exe" }

# 7. The packaged engine pair matches bin\.
Step "Packaged engine pair check"
foreach ($name in @("firelight-apply.exe", "nql-apply.exe")) {
    $packaged = Join-Path $Internal "bin\$name"
    if (-not (Test-Path -LiteralPath $packaged)) { Fail "missing $packaged" }
    if ((Sha256 $packaged) -ne $engineHash) { Fail "$packaged differs from bin\$name" }
}

if ($SkipSmoke) { Step "Done (smoke test skipped): $Out"; exit 0 }

# 8. Smoke test: the built server starts, answers /health with the token,
#    runs a script child as a bundled module, and stops on /shutdown.
Step "Smoke test"
$smokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("neq-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $smokeRoot | Out-Null
$token = [guid]::NewGuid().ToString("N")

$probeIn = Join-Path $smokeRoot "probe-in.txt"
$probeOut = Join-Path $smokeRoot "probe-out.bin"
Set-Content -LiteralPath $probeIn -Value "not a request" -NoNewline
$child = Join-Path $Internal "utils\capture\live_provider_call.py"
$p = Start-Process -FilePath $Exe -ArgumentList @("`"$child`"", "--provider-child") -NoNewWindow -PassThru -Wait `
    -RedirectStandardInput $probeIn -RedirectStandardOutput $probeOut
$head = [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($probeOut), 0, 2)
if ($head -ne "P " -and $head -ne "E ") { Fail "the provider child did not answer with its framing (exit $($p.ExitCode))" }
Step "  provider child: framed answer"

$helpOut = Join-Path $smokeRoot "builder-help.txt"
$builder = Join-Path $Internal "core\generators\combat_builder.py"
$env:NEQ_DATA_DIR = $smokeRoot
Copy-Item -LiteralPath (Join-Path $Internal "config_template.py") -Destination (Join-Path $smokeRoot "config.py")
$p = Start-Process -FilePath $Exe -ArgumentList @("`"$builder`"", "--help") -NoNewWindow -PassThru -Wait -RedirectStandardOutput $helpOut
Remove-Item Env:NEQ_DATA_DIR
if ($p.ExitCode -ne 0 -or -not ((Get-Content -LiteralPath $helpOut -Raw) -match "Build a combat encounter")) { Fail "combat_builder did not run as a bundled module" }
Step "  combat_builder: --help answered"

$env:NEQ_LOCAL_TOKEN = $token
$env:NEQ_DESKTOP = "1"
$serverLog = Join-Path $smokeRoot "server.txt"
$server = Start-Process -FilePath $Exe -ArgumentList @("--serve", "--no-browser", "--port", "0", "--data-dir", "`"$smokeRoot`"") `
    -NoNewWindow -PassThru -RedirectStandardOutput $serverLog -RedirectStandardError (Join-Path $smokeRoot "server-err.txt")
$null = $server.Handle  # keeps ExitCode readable after the process ends
Remove-Item Env:NEQ_LOCAL_TOKEN
Remove-Item Env:NEQ_DESKTOP
$portFile = Join-Path $smokeRoot "run\port"
$headers = @{ "X-NEQ-Local-Token" = $token }
$health = $null
for ($i = 0; $i -lt 240 -and -not $health; $i++) {
    Start-Sleep -Milliseconds 500
    if ($server.HasExited) { Fail "the server exited early (code $($server.ExitCode)); see $serverLog" }
    if (-not (Test-Path -LiteralPath $portFile)) { continue }
    try {
        $port = (Get-Content -LiteralPath $portFile -Raw | ConvertFrom-Json).port
        $h = Invoke-RestMethod -UseBasicParsing -Headers $headers -Uri "http://127.0.0.1:$port/health" -TimeoutSec 5
        if ($h.ready) { $health = $h }
    } catch { }
}
if (-not $health) { $server.Kill(); Fail "/health never reported ready; see $serverLog" }
$version = (Get-Content "VERSION" -Raw).Trim()
if ($health.version -ne $version) { $server.Kill(); Fail "/health version $($health.version), VERSION $version" }
Step "  /health ready, version $($health.version), port $port"
Invoke-WebRequest -UseBasicParsing -Method Post -Headers $headers -Uri "http://127.0.0.1:$port/shutdown" | Out-Null
if (-not $server.WaitForExit(120000)) { $server.Kill(); Fail "the server did not stop after /shutdown" }
if ($server.ExitCode -ne 0) { Fail "the server exited $($server.ExitCode) after /shutdown" }
Step "  /shutdown: exit 0"
Remove-Item -Recurse -Force -LiteralPath $smokeRoot
Step "Done: $Out"
