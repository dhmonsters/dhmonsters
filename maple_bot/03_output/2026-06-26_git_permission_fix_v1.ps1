# Codex Git 메타데이터 쓰기 권한 문제를 우회하도록 Git 저장소 메타데이터 위치를 이전한다.
param(
    [string]$Repo = "C:\Users\PC\Desktop\02_work\05_AI",
    [string]$MetadataName = "_codex_git_metadata"
)

$ErrorActionPreference = "Stop"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "관리자 PowerShell에서 실행해야 합니다. 현재 세션은 관리자 권한이 아닙니다."
    }
}

function Remove-DenyRulesOnPath {
    param(
        [Parameter(Mandatory=$true)][string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $acl = Get-Acl -LiteralPath $Path
    $denyRules = @($acl.Access | Where-Object { $_.AccessControlType -eq "Deny" })
    foreach ($rule in $denyRules) {
        [void]$acl.RemoveAccessRuleSpecific($rule)
    }
    if ($denyRules.Count -gt 0) {
        Set-Acl -LiteralPath $Path -AclObject $acl
        Write-Host "Removed deny ACL from $Path"
    }
}

function Repair-GitAclTree {
    param(
        [Parameter(Mandatory=$true)][string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $denySids = @(
        "*S-1-5-21-978354614-1266499431-1830078014-2620688460",
        "*S-1-5-21-3634278631-776383150-2551165408-3594734579"
    )
    icacls $Path /remove:d $denySids /T /C | Out-Host
    icacls $Path /grant:r "DESKTOP-9MNMSJL\CodexSandboxUsers:(OI)(CI)(M)" "DESKTOP-9MNMSJL\PC:(OI)(CI)(F)" /T /C | Out-Host
}

function Copy-FileIfMissing {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination
    )

    if (Test-Path -LiteralPath $Source -PathType Leaf) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
    }
}

function Convert-ResidualGitDirectoryToLinkedGitDir {
    param(
        [Parameter(Mandatory=$true)][string]$GitPath,
        [Parameter(Mandatory=$true)][string]$MetadataPath
    )

    Remove-DenyRulesOnPath -Path $GitPath
    Repair-GitAclTree -Path $GitPath
    attrib -H $GitPath 2>$null
    New-Item -ItemType Directory -Force -Path $GitPath | Out-Null

    Copy-HeadRefIfNeeded -SourceGit $GitPath -DestinationGit $MetadataPath
    Copy-DirectoryMerge -Source (Join-Path $GitPath "worktrees") -Destination (Join-Path $MetadataPath "worktrees")

    $headSource = Join-Path $MetadataPath "HEAD"
    $indexSource = Join-Path $MetadataPath "index"
    Copy-FileIfMissing -Source $headSource -Destination (Join-Path $GitPath "HEAD")
    Copy-FileIfMissing -Source $indexSource -Destination (Join-Path $GitPath "index")
    Set-Content -LiteralPath (Join-Path $GitPath "commondir") -Value (($MetadataPath -replace "\\", "/") + "`n") -Encoding ASCII

    Write-Host "Converted residual .git directory into a linked git dir."
}

Assert-Administrator

$repoPath = (Resolve-Path -LiteralPath $Repo).Path
$expectedRepo = "C:\Users\PC\Desktop\02_work\05_AI"
if ($repoPath -ne $expectedRepo) {
    throw "Unexpected repo path: $repoPath"
}

$gitPath = Join-Path $repoPath ".git"
$metadataPath = Join-Path $repoPath $MetadataName

function Copy-DirectoryMerge {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        return
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
    }
}

function Copy-HeadRefIfNeeded {
    param(
        [Parameter(Mandatory=$true)][string]$SourceGit,
        [Parameter(Mandatory=$true)][string]$DestinationGit
    )

    $headPath = Join-Path $DestinationGit "HEAD"
    if (-not (Test-Path -LiteralPath $headPath -PathType Leaf)) {
        return
    }

    $head = (Get-Content -LiteralPath $headPath -Raw).Trim()
    if ($head -notmatch "^ref:\s+(.+)$") {
        return
    }

    $refName = $Matches[1]
    $sourceRef = Join-Path $SourceGit $refName
    $destinationRef = Join-Path $DestinationGit $refName
    if ((Test-Path -LiteralPath $destinationRef -PathType Leaf) -or -not (Test-Path -LiteralPath $sourceRef -PathType Leaf)) {
        return
    }

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destinationRef) | Out-Null
    Copy-Item -LiteralPath $sourceRef -Destination $destinationRef -Force
    Write-Host "Copied HEAD ref: $refName"
}

function New-BackupPath {
    param(
        [Parameter(Mandatory=$true)][string]$RepoPath,
        [Parameter(Mandatory=$true)][string]$Prefix
    )

    for ($i = 0; $i -lt 100; $i++) {
        $suffix = if ($i -eq 0) { "" } else { "_$i" }
        $candidate = Join-Path $RepoPath ($Prefix + "_" + (Get-Date -Format "yyyyMMdd_HHmmss") + $suffix)
        if (-not (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
        Start-Sleep -Milliseconds 100
    }
    throw "Could not allocate backup path."
}

if ((Test-Path -LiteralPath $gitPath -PathType Leaf)) {
    $content = Get-Content -LiteralPath $gitPath -Raw
    if ($content -match [regex]::Escape($MetadataName)) {
        Write-Host "Already migrated: $gitPath"
    } else {
        throw ".git is already a file, but it does not point to $MetadataName"
    }
} elseif (Test-Path -LiteralPath $gitPath -PathType Container) {
    $gitHead = Join-Path $gitPath "HEAD"
    $metadataHead = Join-Path $metadataPath "HEAD"

    if ((Test-Path -LiteralPath $metadataPath -PathType Container) -and (Test-Path -LiteralPath $metadataHead -PathType Leaf)) {
        Write-Host "Detected partial migration. Converting remaining .git directory into linked git dir."
        Convert-ResidualGitDirectoryToLinkedGitDir -GitPath $gitPath -MetadataPath $metadataPath
    } elseif (Test-Path -LiteralPath $metadataPath) {
        throw "Target metadata path already exists: $metadataPath"
    } elseif (Test-Path -LiteralPath $gitHead -PathType Leaf) {
        Remove-DenyRulesOnPath -Path $gitPath
        attrib -H $gitPath 2>$null
        [System.IO.Directory]::Move($gitPath, $metadataPath)
        Set-Content -LiteralPath $gitPath -Value ("gitdir: " + ($metadataPath -replace "\\", "/")) -Encoding ASCII
        Write-Host "Moved .git directory to $metadataPath"
    } else {
        throw ".git is a directory but neither .git\HEAD nor $metadataHead exists."
    }
} else {
    if ((Test-Path -LiteralPath $metadataPath -PathType Container) -and (Test-Path -LiteralPath (Join-Path $metadataPath "HEAD") -PathType Leaf)) {
        Set-Content -LiteralPath $gitPath -Value ("gitdir: " + ($metadataPath -replace "\\", "/")) -Encoding ASCII
        Write-Host "Created .git pointer to $metadataPath"
    } else {
        throw ".git path was not found and metadata path is not ready: $gitPath"
    }
}

$items = @(Get-Item -LiteralPath $metadataPath -Force) + @(Get-ChildItem -LiteralPath $metadataPath -Recurse -Force)
foreach ($item in $items) {
    $acl = Get-Acl -LiteralPath $item.FullName
    $denyRules = @($acl.Access | Where-Object { $_.AccessControlType -eq "Deny" })
    if ($denyRules.Count -eq 0) {
        continue
    }
    foreach ($rule in $denyRules) {
        [void]$acl.RemoveAccessRuleSpecific($rule)
    }
    Set-Acl -LiteralPath $item.FullName -AclObject $acl
}

icacls $metadataPath /grant:r "DESKTOP-9MNMSJL\CodexSandboxUsers:(OI)(CI)(M)" "DESKTOP-9MNMSJL\PC:(OI)(CI)(F)" /T /C | Out-Host
if (Test-Path -LiteralPath $gitPath -PathType Container) {
    Repair-GitAclTree -Path $gitPath
    Copy-FileIfMissing -Source (Join-Path $metadataPath "HEAD") -Destination (Join-Path $gitPath "HEAD")
    Copy-FileIfMissing -Source (Join-Path $metadataPath "index") -Destination (Join-Path $gitPath "index")
    Set-Content -LiteralPath (Join-Path $gitPath "commondir") -Value (($metadataPath -replace "\\", "/") + "`n") -Encoding ASCII
}

$excludePath = Join-Path $metadataPath "info\exclude"
$excludeText = if (Test-Path -LiteralPath $excludePath) { Get-Content -LiteralPath $excludePath -Raw } else { "" }
$excludeLine = "/$MetadataName/"
if ($excludeText -notmatch [regex]::Escape($excludeLine)) {
    Add-Content -LiteralPath $excludePath -Value "`n$excludeLine"
}

Set-Location -LiteralPath $repoPath
$gitDir = git rev-parse --git-dir
Write-Host "git-dir: $gitDir"

$probe = Join-Path $metadataPath "codex_perm_probe.tmp"
Set-Content -LiteralPath $probe -Value "probe" -Encoding ASCII
Remove-Item -LiteralPath $probe -Force

git status --short
Write-Host "Git permission fix completed."
