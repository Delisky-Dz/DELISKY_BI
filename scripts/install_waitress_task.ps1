param(
    [ValidateSet("Check", "Install")]
    [string]$Mode = "Check",

    [switch]$StartNow
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TaskName = "DELISKY Production Waitress"
$Project = Split-Path $PSScriptRoot -Parent
$Launcher = Join-Path $PSScriptRoot "start_production_waitress.ps1"
$PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$LauncherArguments = (
    '-NoProfile -ExecutionPolicy Bypass -File "{0}"'
) -f $Launcher

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)

    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

Write-Host "=== DELISKY WAITRESS TASK ==="
Write-Host "MODE=$Mode"
Write-Host "PROJECT=$Project"
Write-Host "LAUNCHER_EXISTS=$(Test-Path -LiteralPath $Launcher)"
Write-Host "POWERSHELL_EXISTS=$(Test-Path -LiteralPath $PowerShell)"

if (-not (Test-Path -LiteralPath $Launcher)) {
    throw "WAITRESS_LAUNCHER_NOT_FOUND: $Launcher"
}

if (-not (Test-Path -LiteralPath $PowerShell)) {
    throw "POWERSHELL_NOT_FOUND: $PowerShell"
}

if ($Mode -eq "Check") {
    try {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
        $action = @($task.Actions)[0]

        $actionMatches = (
            $action.Execute -eq $PowerShell -and
            $action.Arguments -eq $LauncherArguments -and
            $action.WorkingDirectory -eq $Project
        )

        Write-Host "TASK_FOUND=True"
        Write-Host "TASK_STATE=$($task.State)"
        Write-Host "RUN_AS=$($task.Principal.UserId)"
        Write-Host "LAST_RUN_TIME=$($info.LastRunTime)"
        Write-Host "LAST_TASK_RESULT=$($info.LastTaskResult)"
        Write-Host "ACTION_MATCHES_EXPECTED=$actionMatches"
        Write-Host "ACTION_EXECUTE=$($action.Execute)"
        Write-Host "ACTION_ARGUMENTS=$($action.Arguments)"
        Write-Host "ACTION_WORKING_DIRECTORY=$($action.WorkingDirectory)"
    }
    catch {
        Write-Host "TASK_CHECK_FAILED=True"
        Write-Host "TASK_CHECK_ERROR=$($_.Exception.Message)"
        Write-Host (
            "Run this script from an Administrator PowerShell for " +
            "authoritative task visibility."
        )
    }

    exit 0
}

if (-not (Test-IsAdministrator)) {
    throw "ADMINISTRATOR_PRIVILEGES_REQUIRED"
}

$action = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument $LauncherArguments `
    -WorkingDirectory $Project

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description (
        "Starts DELISKY Production Waitress only after branch, working-tree, " +
        "origin/main, static-manifest and Django safety checks pass."
    ) `
    -Force |
    Out-Null

Write-Host "TASK_INSTALLED=True"

if ($StartNow) {
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 5
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
$installedAction = @($task.Actions)[0]

$actionMatches = (
    $installedAction.Execute -eq $PowerShell -and
    $installedAction.Arguments -eq $LauncherArguments -and
    $installedAction.WorkingDirectory -eq $Project
)

Write-Host "TASK_STATE=$($task.State)"
Write-Host "RUN_AS=$($task.Principal.UserId)"
Write-Host "LAST_RUN_TIME=$($info.LastRunTime)"
Write-Host "LAST_TASK_RESULT=$($info.LastTaskResult)"
Write-Host "ACTION_MATCHES_EXPECTED=$actionMatches"

if (-not $actionMatches) {
    throw "WAITRESS_TASK_ACTION_MISMATCH"
}

if ($StartNow) {
    if ($task.State -eq "Running") {
        Write-Host "START_SMOKE=PASS"
    }
    elseif ($info.LastTaskResult -ne 0) {
        throw (
            "WAITRESS_TASK_START_FAILED: " +
            "$($info.LastTaskResult)"
        )
    }
}
