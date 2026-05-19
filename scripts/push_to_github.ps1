param(
    [string]$RepositoryUrl = "https://github.com/kevinmxk/ashare-quant-tool.git",
    [string]$Branch = "main",
    [string]$CommitMessage = "Initial project upload",
    [switch]$SkipCommit,
    [switch]$VerboseGit
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    if ($VerboseGit) {
        Write-Host ("git " + ($Args -join " ")) -ForegroundColor Cyan
    }

    & git @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($Args -join ' ')"
    }
}

Set-Location $ProjectRoot

Write-Host "Project root: $ProjectRoot" -ForegroundColor Green

if (-not (Test-Path (Join-Path $ProjectRoot ".git"))) {
    Write-Host "Initializing local git repository..." -ForegroundColor Yellow
    Invoke-Git -Args @("init")
}

$currentBranch = (& git branch --show-current).Trim()
if (-not $currentBranch) {
    Write-Host "Creating branch $Branch..." -ForegroundColor Yellow
    Invoke-Git -Args @("checkout", "-b", $Branch)
} elseif ($currentBranch -ne $Branch) {
    Write-Host "Switching branch to $Branch..." -ForegroundColor Yellow
    try {
        Invoke-Git -Args @("checkout", $Branch)
    } catch {
        Invoke-Git -Args @("checkout", "-b", $Branch)
    }
}

$remoteUrl = ""
try {
    $remoteUrl = (& git remote get-url origin).Trim()
} catch {
    $remoteUrl = ""
}

if (-not $remoteUrl) {
    Write-Host "Adding remote origin..." -ForegroundColor Yellow
    Invoke-Git -Args @("remote", "add", "origin", $RepositoryUrl)
} elseif ($remoteUrl -ne $RepositoryUrl) {
    Write-Host "Updating remote origin..." -ForegroundColor Yellow
    Invoke-Git -Args @("remote", "set-url", "origin", $RepositoryUrl)
}

Write-Host "Staging project files..." -ForegroundColor Yellow
Invoke-Git -Args @("add", ".")

if (-not $SkipCommit) {
    $hasChanges = (& git status --porcelain).Trim()
    if ($hasChanges) {
        Write-Host "Creating commit..." -ForegroundColor Yellow
        Invoke-Git -Args @("commit", "-m", $CommitMessage)
    } else {
        Write-Host "No staged changes to commit." -ForegroundColor DarkYellow
    }
}

Write-Host "Pushing branch $Branch to origin..." -ForegroundColor Yellow
Invoke-Git -Args @("push", "-u", "origin", $Branch)

Write-Host "Push completed." -ForegroundColor Green

