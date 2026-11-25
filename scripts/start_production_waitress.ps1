param(
    [ValidateSet("127.0.0.1:8080")]
    [string]$Listen = "127.0.0.1:8080"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Project = Split-Path $PSScriptRoot -Parent
# Resolve imports and .env consistently even under Task Scheduler/System32.
Set-Location -LiteralPath $Project
$LogDirectory = Join-Path $Project "logs"
New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
$LogPath = Join-Path $LogDirectory "production-waitress.log"
function Open-WaitressTranscript {
    param([switch]$AlreadyOpen)
    if ((Test-Path -LiteralPath $LogPath) -and (Get-Item -LiteralPath $LogPath).Length -gt 10MB) {
        if ($AlreadyOpen) { Stop-Transcript | Out-Null }
        Move-Item -LiteralPath $LogPath -Destination "$LogPath.1" -Force
    }
    elseif ($AlreadyOpen) { return }
    Start-Transcript -LiteralPath $LogPath -Append | Out-Null
    Write-Host "SUPERVISOR_PID=$PID"
}

Open-WaitressTranscript
try {
Write-Host "START_TIMESTAMP=$([DateTimeOffset]::Now.ToString('o'))"
$RequiredBranch = "main"
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
        & $Git --no-optional-locks -C $Project @Arguments 2>&1
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
Write-Host "BRANCH=$currentBranch"
Write-Host "HEAD=$head"

# Override inherited DEV selection before dotenv/settings are imported.
$env:DB_NAME = "delisky_bi"
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
Write-Host "DB_SAFETY=PASS EXPECTED=delisky_bi SETTINGS=config.settings.production"

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
$maxRecoveryAttempts = 10
$recoveryDelaySeconds = 15
$stableRuntimeSeconds = 300
$recoveryAttempt = 0
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $Python
$startInfo.WorkingDirectory = $Project
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.Arguments = @(
    '-m', 'waitress',
    "--listen=$Listen",
    "--threads=4",
    "--trusted-proxy=127.0.0.1",
    "--trusted-proxy-headers=x-forwarded-proto",
    "config.wsgi:application"
) -join ' '

Write-Host "WAITRESS_THREADS=4"
Write-Host "LISTEN=$Listen"

while ($true) {
    # After a synchronous child exit, any remaining listener has unknown ownership.
    $listeners = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    if (@($listeners | Where-Object { $_.Port -eq 8080 -and $_.Address.ToString() -in @("127.0.0.1", "0.0.0.0", "::") }).Count) {
        throw "WAITRESS_PORT_IN_USE: 127.0.0.1:8080"
    }

    Write-Host "WAITRESS_STARTING=True RECOVERY_START_ATTEMPT=$recoveryAttempt"
    $runtime = [Diagnostics.Stopwatch]::StartNew()
    $child = [Diagnostics.Process]::Start($startInfo)
    try {
        Write-Host "WAITRESS_CHILD_PID=$($child.Id) CHILD_START_TIMESTAMP=$([DateTimeOffset]::Now.ToString('o'))"
        $child.WaitForExit()
        $runtime.Stop()
        $childExitCode = $child.ExitCode
    }
    finally { $child.Dispose() }

    Write-Host "CHILD_EXIT_TIMESTAMP=$([DateTimeOffset]::Now.ToString('o')) RUNTIME_SECONDS=$([int][Math]::Floor($runtime.Elapsed.TotalSeconds))"
    Write-Host "WAITRESS_EXIT_CODE=$childExitCode WAITRESS_EXIT_UNEXPECTED=True"
    if ($runtime.Elapsed.TotalSeconds -ge $stableRuntimeSeconds) {
        $recoveryAttempt = 0
        Write-Host "RECOVERY_BUDGET_RESET=True"
    }
    if ($recoveryAttempt -ge $maxRecoveryAttempts) {
        throw "RECOVERY_BUDGET_EXHAUSTED: $maxRecoveryAttempts consecutive retries"
    }

    $recoveryAttempt++
    Write-Host "RECOVERY_ATTEMPT=$recoveryAttempt RECOVERY_DELAY_SECONDS=$recoveryDelaySeconds"
    Start-Sleep -Seconds $recoveryDelaySeconds
    Open-WaitressTranscript -AlreadyOpen
}

}
catch {
    # Guard messages contain identifiers/paths only; never dump environment.
    Write-Host "FATAL_TIMESTAMP=$([DateTimeOffset]::Now.ToString('o'))"
    Write-Host "FATAL=$($_.Exception.Message)"
    $launcherExitCode = 1
}
finally {
    Write-Host "STOP_TIMESTAMP=$([DateTimeOffset]::Now.ToString('o'))"
    Stop-Transcript | Out-Null
}
exit $launcherExitCode
