# Puzzle2 포터블 EXE를 빌드하고 검증용 ZIP으로 압축한다.
param(
    [string]$Python = "C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputRoot = Join-Path $ProjectRoot "03_output"
$BuildRoot = Join-Path $OutputRoot "2026-08-10_puzzle2_portable_build_v1"
$DistRoot = Join-Path $BuildRoot "dist"
$WorkRoot = Join-Path $BuildRoot "work"
$PortableRoot = Join-Path $DistRoot "Puzzle2_Portable"
$ZipPath = Join-Path $OutputRoot "2026-08-10_puzzle2_portable_v1.zip"

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
    (Join-Path $ProjectRoot "puzzle2_portable.spec")
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
Puzzle2 SOT Portable Validation Tool

1. Extract the ZIP completely.
2. Run Puzzle2_Portable\puzzle2.exe.
3. Mouse output always starts OFF.
4. Check the tracking overlay before enabling mouse output.

Requirements
- Windows 10/11 64-bit
- NVIDIA GPU with a compatible current driver
- 1280x720 game client

Logs
- The sessions folder next to puzzle2.exe
"@
Set-Content -LiteralPath (Join-Path $PortableRoot "README.txt") -Value $Readme -Encoding ASCII

$PortableExe = Join-Path $PortableRoot "puzzle2.exe"
$SmokeProcess = Start-Process `
    -FilePath $PortableExe `
    -WorkingDirectory $PortableRoot `
    -WindowStyle Hidden `
    -PassThru
Start-Sleep -Seconds 12
$SmokeProcess.Refresh()
if ($SmokeProcess.HasExited -or -not $SmokeProcess.Responding) {
    throw "Portable EXE smoke test failed."
}
Stop-Process -Id $SmokeProcess.Id -Force

Compress-Archive -LiteralPath $PortableRoot -DestinationPath $ZipPath -CompressionLevel Optimal

[System.Reflection.Assembly]::LoadWithPartialName("System.IO.Compression.FileSystem") | Out-Null
$Archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    $EntryNames = @($Archive.Entries | ForEach-Object { $_.FullName.Replace("\", "/") })
    $RequiredEntries = @(
        "Puzzle2_Portable/puzzle2.exe",
        "Puzzle2_Portable/vendor/live_core.py",
        "Puzzle2_Portable/vendor/triangle_models/triangle_guard_v6496.pt"
    )
    foreach ($Required in $RequiredEntries) {
        if ($Required -notin $EntryNames) {
            throw "Portable ZIP verification failed. Missing: $Required"
        }
    }
}
finally {
    $Archive.Dispose()
}

Write-Host "PORTABLE_EXE=$PortableExe"
Write-Host "PORTABLE_ZIP=$ZipPath"
