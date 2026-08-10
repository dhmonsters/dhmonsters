# GT 1030 CUDA 검사 EXE를 빌드하고 자체 검사 후 ZIP으로 압축한다.
param(
    [string]$Python = "C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputRoot = Join-Path $ProjectRoot "03_output"
$BuildRoot = Join-Path $OutputRoot "2026-08-10_gt1030_cuda_probe_build_v1"
$DistRoot = Join-Path $BuildRoot "dist"
$WorkRoot = Join-Path $BuildRoot "work"
$PortableRoot = Join-Path $DistRoot "GT1030_CUDA_Probe"
$ZipPath = Join-Path $OutputRoot "2026-08-10_gt1030_cuda_probe_v1.zip"

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
    (Join-Path $ProjectRoot "gt1030_cuda_probe.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

foreach ($Name in @("nvrtc64_120_0.dll", "nvrtc-builtins64_128.dll")) {
    $InternalPath = Join-Path $PortableRoot ("_internal\" + $Name)
    $PortablePath = Join-Path $PortableRoot $Name
    if (-not (Test-Path -LiteralPath $InternalPath -PathType Leaf)) {
        throw "NVRTC payload is missing: $InternalPath"
    }
    Move-Item -LiteralPath $InternalPath -Destination $PortablePath
}

$Readme = @"
GT 1030 CUDA Compatibility Probe

1. Extract this ZIP completely.
2. Double-click GT1030_CUDA_Probe.exe.
3. Wait for the PASS, SLOW, or FAIL result window.
4. Send gt1030_probe_report.json back for review.

This probe does not move the mouse and does not access the game process.
It tests CUDA kernel execution, dedicated VRAM, 512 MB allocation, and a
Puzzle2-sized image-filter workload.
"@
Set-Content -LiteralPath (Join-Path $PortableRoot "README.txt") -Value $Readme -Encoding ASCII

$PortableExe = Join-Path $PortableRoot "GT1030_CUDA_Probe.exe"
$ProbeProcess = Start-Process `
    -FilePath $PortableExe `
    -ArgumentList "--no-dialog" `
    -WorkingDirectory $PortableRoot `
    -Wait `
    -PassThru
if ($ProbeProcess.ExitCode -ne 0) {
    throw "Packaged CUDA probe failed with exit code $($ProbeProcess.ExitCode)"
}
$ReportPath = Join-Path $PortableRoot "gt1030_probe_report.json"
$Report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
if ($Report.status -ne "PASS") {
    throw "Packaged CUDA probe did not pass: $($Report.status)"
}

Compress-Archive -LiteralPath $PortableRoot -DestinationPath $ZipPath -CompressionLevel Optimal

[System.Reflection.Assembly]::LoadWithPartialName("System.IO.Compression.FileSystem") | Out-Null
$Archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    $EntryNames = @($Archive.Entries | ForEach-Object { $_.FullName.Replace("\", "/") })
    $RequiredEntries = @(
        "GT1030_CUDA_Probe/GT1030_CUDA_Probe.exe",
        "GT1030_CUDA_Probe/nvrtc64_120_0.dll",
        "GT1030_CUDA_Probe/nvrtc-builtins64_128.dll",
        "GT1030_CUDA_Probe/README.txt"
    )
    foreach ($Required in $RequiredEntries) {
        if ($Required -notin $EntryNames) {
            throw "Probe ZIP verification failed. Missing: $Required"
        }
    }
}
finally {
    $Archive.Dispose()
}

Write-Host "PROBE_EXE=$PortableExe"
Write-Host "PROBE_ZIP=$ZipPath"
