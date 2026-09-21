param(
    [string]$Listen = "127.0.0.1:8080"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Project = Split-Path $PSScriptRoot -Parent
$RequiredBranch = "main"
$Waitress = Join-Path $Project ".venv\Scripts\waitress-serve.exe"
$Python = Join-Path $Project ".venv\Scripts\python.exe"
$StaticVerifier = Join-Path $Project "scripts\verify_static_manifest.py"
$Git = "C:\Program Files\Git\cmd\git.exe"

if (-not (Test-Path -LiteralPath $Git)) {
    $gitCommand = Get-Command git.exe -ErrorAction SilentlyContinue

    if ($null -eq $gitCommand) {
        throw "GIT_NOT_FOUND"
    }

    $Git = $gitCommand.Source
}

function Invoke-GitText {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = @(
        & $Git -C $Project @Arguments 2>&1
    )
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        throw (
            "Git command failed: git {0} :: {1}" -f
            ($Arguments -join " "),
            ($output -join " ")
        )
    }

    return ($output -join "`n").Trim()
}

Write-Host "=== DELISKY PRODUCTION WAITRESS START ==="
Write-Host "PROJECT=$Project"
Write-Host "REQUIRED_BRANCH=$RequiredBranch"

foreach ($requiredFile in @(
    $Waitress,
    $Python,
    $StaticVerifier
)) {
    if (-not (Test-Path -LiteralPath $requiredFile)) {
        throw "REQUIRED_FILE_NOT_FOUND: $requiredFile"
    }
}

Write-Host "GIT=$Git"

$currentBranch = Invoke-GitText -Arguments @(
    "branch",
    "--show-current"
)

if ($currentBranch -ne $RequiredBranch) {
    throw (
        "PRODUCTION_BRANCH_GUARD_FAILED: expected '$RequiredBranch', " +
        "got '$currentBranch'."
    )
}

$workingTreeStatus = Invoke-GitText -Arguments @(
    "status",
    "--porcelain"
)

if ($workingTreeStatus) {
    throw "PRODUCTION_WORKING_TREE_NOT_CLEAN"
}

$head = Invoke-GitText -Arguments @(
    "rev-parse",
    "HEAD"
)

$originMain = Invoke-GitText -Arguments @(
    "rev-parse",
    "refs/remotes/origin/main"
)

if ($head -ne $originMain) {
    throw (
        "PRODUCTION_HEAD_GUARD_FAILED: HEAD=$head " +
        "origin/main=$originMain"
    )
}

Write-Host "BRANCH_GUARD=PASS"
Write-Host "WORKING_TREE_GUARD=PASS"
Write-Host "HEAD_GUARD=PASS"
Write-Host "HEAD=$head"

& $Python $StaticVerifier

if ($LASTEXITCODE -ne 0) {
    throw (
        "PRODUCTION_STATIC_MANIFEST_GUARD_FAILED: " +
        "exit code $LASTEXITCODE"
    )
}

Write-Host "STATIC_MANIFEST_GUARD=PASS"

& $Python `
    (Join-Path $Project "manage.py") `
    check `
    --settings=config.settings.production

if ($LASTEXITCODE -ne 0) {
    throw (
        "PRODUCTION_DJANGO_CHECK_FAILED: " +
        "exit code $LASTEXITCODE"
    )
}

Write-Host "DJANGO_CHECK=PASS"
Write-Host "WAITRESS_STARTING=True"
Write-Host "LISTEN=$Listen"

& $Waitress `
    "--listen=$Listen" `
    "--trusted-proxy=127.0.0.1" `
    "--trusted-proxy-headers=x-forwarded-proto" `
    "config.wsgi:application"

$waitressExitCode = $LASTEXITCODE

Write-Host "WAITRESS_EXIT_CODE=$waitressExitCode"

exit $waitressExitCode
