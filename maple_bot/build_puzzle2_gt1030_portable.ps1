# sm_61 지원 Puzzle2 GT1030 배포본을 빌드하고 자체 검사 후 ZIP으로 압축한다.
param(
    [string]$Python = "C:\Users\PC\Desktop\02_work\05_AI\maple_bot\03_output\2026-08-10_gt1030_torch_env_v1\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputRoot = Join-Path $ProjectRoot "03_output"
$BuildRoot = Join-Path $OutputRoot "2026-08-10_puzzle2_gt1030_portable_build_v1"
$DistRoot = Join-Path $BuildRoot "dist"
$WorkRoot = Join-Path $BuildRoot "work"
$PortableRoot = Join-Path $DistRoot "Puzzle2_GT1030"
$ZipPath = Join-Path $OutputRoot "2026-08-10_puzzle2_gt1030_portable_v1.zip"
$SelfCheckPath = Join-Path $PortableRoot "gt1030_runtime_check.json"
$ExpectedTempEnv = Join-Path $OutputRoot "2026-08-10_gt1030_torch_env_v1"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "GT1030 build Python is missing: $Python"
}
if (Test-Path -LiteralPath $BuildRoot) {
    Remove-Item -LiteralPath $BuildRoot -Recurse -Force
}
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $DistRoot `
    --workpath $WorkRoot `
    (Join-Path $ProjectRoot "puzzle2_gt1030_portable.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

$InternalVendor = Join-Path $PortableRoot "_internal\vendor"
$PortableVendor = Join-Path $PortableRoot "vendor"
if (-not (Test-Path -LiteralPath $InternalVendor -PathType Container)) {
    throw "PyInstaller vendor payload is missing: $InternalVendor"
}
Move-Item -LiteralPath $InternalVendor -Destination $PortableVendor

$Readme = @"
Puzzle2 GT1030 Portable Validation Tool

1. Extract the ZIP completely.
2. Run GT1030_SELF_CHECK.cmd first.
3. PASS means sm_61 CUDA and the V6497 model inference both worked.
4. Run puzzle2_gt1030.exe.
5. Mouse output always starts OFF.

Requirements
- Windows 10/11 64-bit
- NVIDIA GeForce GT 1030 4GB or newer
- A current NVIDIA driver
- 1280x720 game client

Logs
- The sessions folder next to puzzle2_gt1030.exe
"@
Set-Content -LiteralPath (Join-Path $PortableRoot "README.txt") -Value $Readme -Encoding ASCII

$SelfCheckCommand = @"
@echo off
cd /d "%~dp0"
puzzle2_gt1030.exe --runtime-self-check gt1030_runtime_check.json --required-arch sm_61
if errorlevel 1 (
  echo.
  echo GT1030 runtime check FAILED.
  if exist gt1030_runtime_check.json type gt1030_runtime_check.json
  pause
  exit /b 1
)
echo.
echo GT1030 runtime check PASSED.
type gt1030_runtime_check.json
pause
"@
Set-Content `
    -LiteralPath (Join-Path $PortableRoot "GT1030_SELF_CHECK.cmd") `
    -Value $SelfCheckCommand `
    -Encoding ASCII

$PortableExe = Join-Path $PortableRoot "puzzle2_gt1030.exe"
$SelfCheckProcess = Start-Process `
    -FilePath $PortableExe `
    -ArgumentList @(
        "--runtime-self-check",
        $SelfCheckPath,
        "--required-arch",
        "sm_61"
    ) `
    -WorkingDirectory $PortableRoot `
    -WindowStyle Hidden `
    -Wait `
    -PassThru
if ($SelfCheckProcess.ExitCode -ne 0) {
    throw "Packaged GT1030 runtime check failed with exit code $($SelfCheckProcess.ExitCode)"
}
$SelfCheck = Get-Content -LiteralPath $SelfCheckPath -Raw | ConvertFrom-Json
if ($SelfCheck.status -ne "PASS") {
    throw "Packaged GT1030 runtime report did not pass."
}
if ($SelfCheck.metrics.required_arch -ne "sm_61") {
    throw "Packaged GT1030 runtime report did not check sm_61."
}
if (-not $SelfCheck.metrics.model_inference_ok) {
    throw "Packaged V6497 model inference did not run."
}

if (Test-Path -LiteralPath $WorkRoot) {
    Remove-Item -LiteralPath $WorkRoot -Recurse -Force
}
$ResolvedPython = (Resolve-Path -LiteralPath $Python).Path
$ResolvedExpectedPython = Join-Path $ExpectedTempEnv "Scripts\python.exe"
if ($ResolvedPython -eq $ResolvedExpectedPython -and (Test-Path -LiteralPath $ExpectedTempEnv)) {
    Remove-Item -LiteralPath $ExpectedTempEnv -Recurse -Force
}

Compress-Archive `
    -LiteralPath $PortableRoot `
    -DestinationPath $ZipPath `
    -CompressionLevel Optimal

[System.Reflection.Assembly]::LoadWithPartialName("System.IO.Compression.FileSystem") | Out-Null
$Archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    $EntryNames = @($Archive.Entries | ForEach-Object { $_.FullName.Replace("\", "/") })
    $RequiredEntries = @(
        "Puzzle2_GT1030/puzzle2_gt1030.exe",
        "Puzzle2_GT1030/GT1030_SELF_CHECK.cmd",
        "Puzzle2_GT1030/gt1030_runtime_check.json",
        "Puzzle2_GT1030/vendor/live_core.py",
        "Puzzle2_GT1030/vendor/triangle_models/triangle_guard_v6496.pt"
    )
    foreach ($Required in $RequiredEntries) {
        if ($Required -notin $EntryNames) {
            throw "GT1030 ZIP verification failed. Missing: $Required"
        }
    }
}
finally {
    $Archive.Dispose()
}

$Hash = Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256
Write-Host "GT1030_PORTABLE_EXE=$PortableExe"
Write-Host "GT1030_PORTABLE_ZIP=$ZipPath"
Write-Host "GT1030_PORTABLE_SHA256=$($Hash.Hash)"
