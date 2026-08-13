# sm_61 이상을 지원하는 Puzzle2 GPU 공용 배포본을 빌드하고 검사한다.
param(
    [string]$Python = "C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputRoot = Join-Path $ProjectRoot "03_output"
$BuildRoot = Join-Path $OutputRoot "2026-08-13_puzzle2_gpu_portable_build_v3"
$DistRoot = Join-Path $BuildRoot "dist"
$WorkRoot = Join-Path $BuildRoot "work"
$PortableRoot = Join-Path $DistRoot "Puzzle2_GPU"
$ZipPath = Join-Path $OutputRoot "2026-08-13_puzzle2_gpu_portable_v3.zip"
$SelfCheckPath = Join-Path $PortableRoot "gt1030_runtime_check.json"
$InputCheckPath = Join-Path $PortableRoot "interception_module_check.json"

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
Puzzle2 GPU Continuous Monitor

1. Extract the ZIP completely.
2. Install the Interception driver and reboot Windows.
3. Run GPU_SELF_CHECK.cmd first.
4. PASS means sm_61 CUDA, the triangle model, and the model-free V6497 owner guard connection worked.
5. Run puzzle2_gpu.exe as administrator.
6. Mouse output always starts OFF.
7. Solver Start watches continuously. F12 or Solver Stop ends it.
8. Old session logs are removed when Solver Start begins a new run.

Requirements
- Windows 10/11 64-bit
- NVIDIA GeForce GT 1030 4GB or RTX 4060
- A current NVIDIA driver
- Interception kernel driver
- 1280x720 game client

Logs
- The sessions folder next to puzzle2_gpu.exe
"@
Set-Content -LiteralPath (Join-Path $PortableRoot "README.txt") -Value $Readme -Encoding ASCII

$SelfCheckCommand = @"
@echo off
cd /d "%~dp0"
puzzle2_gpu.exe --runtime-self-check gt1030_runtime_check.json --required-arch sm_61
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
    -LiteralPath (Join-Path $PortableRoot "GPU_SELF_CHECK.cmd") `
    -Value $SelfCheckCommand `
    -Encoding ASCII

$PortableExe = Join-Path $PortableRoot "puzzle2_gpu.exe"
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
if ($SelfCheck.metrics.owner_connection.mode -ne "CLASSICAL_TEMPORAL_OWNER_GUARD") {
    throw "Packaged V6497 owner guard mode is incorrect."
}
if (-not $SelfCheck.metrics.owner_connection.owner_guard_constructed) {
    throw "Packaged V6497 owner guard was not constructed."
}
if (-not $SelfCheck.metrics.owner_connection.owner_apply_connected) {
    throw "Packaged V6497 owner guard apply path is missing."
}
if ($SelfCheck.metrics.owner_connection.deep_checkpoint_required) {
    throw "Packaged V6497 unexpectedly requires a deep owner checkpoint."
}

$InputCheckProcess = Start-Process `
    -FilePath $PortableExe `
    -ArgumentList @("--input-module-check", $InputCheckPath) `
    -WorkingDirectory $PortableRoot `
    -WindowStyle Hidden `
    -Wait `
    -PassThru
if ($InputCheckProcess.ExitCode -ne 0) {
    throw "Packaged Interception module check failed with exit code $($InputCheckProcess.ExitCode)"
}
$InputCheck = Get-Content -LiteralPath $InputCheckPath -Raw | ConvertFrom-Json
if ($InputCheck.status -ne "PASS") {
    throw "Packaged Interception module report did not pass."
}

if (Test-Path -LiteralPath $WorkRoot) {
    Remove-Item -LiteralPath $WorkRoot -Recurse -Force
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
        "Puzzle2_GPU/puzzle2_gpu.exe",
        "Puzzle2_GPU/GPU_SELF_CHECK.cmd",
        "Puzzle2_GPU/gt1030_runtime_check.json",
        "Puzzle2_GPU/interception_module_check.json",
        "Puzzle2_GPU/vendor/live_core.py",
        "Puzzle2_GPU/vendor/triangle_models/triangle_guard_v6496.pt"
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
Remove-Item -LiteralPath $BuildRoot -Recurse -Force
Write-Host "GPU_PORTABLE_ZIP=$ZipPath"
Write-Host "GPU_PORTABLE_SHA256=$($Hash.Hash)"
