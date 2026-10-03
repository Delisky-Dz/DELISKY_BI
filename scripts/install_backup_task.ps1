param(
    [ValidateSet("Check", "Install")]
    [string]$Mode = "Check",

    [switch]$StartNow
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TaskName = "DELISKY Daily Backup"
$Project = Split-Path $PSScriptRoot -Parent
$BackupScript = Join-Path $PSScriptRoot "backup_delisky.ps1"
$PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$BackupArguments = (
    '-NoProfile -ExecutionPolicy Bypass -File "{0}" ' +
    '-DjangoSettings "config.settings.production"'
) -f $BackupScript

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)

    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Wait-BackupTask {
    param(
        [int]$TimeoutSeconds = 300
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    do {
        Start-Sleep -Seconds 2
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop

        if ($task.State -ne "Running") {
            return
        }

        if ((Get-Date) -ge $deadline) {
            throw "BACKUP_TASK_TIMEOUT"
        }
    }
    while ($true)
}

Write-Host "=== DELISKY BACKUP TASK ==="
Write-Host "MODE=$Mode"
Write-Host "PROJECT=$Project"
Write-Host "BACKUP_SCRIPT_EXISTS=$(Test-Path -LiteralPath $BackupScript)"
Write-Host "POWERSHELL_EXISTS=$(Test-Path -LiteralPath $PowerShell)"

if (-not (Test-Path -LiteralPath $BackupScript)) {
    throw "BACKUP_SCRIPT_NOT_FOUND: $BackupScript"
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
            $action.Arguments -eq $BackupArguments -and
            $action.WorkingDirectory -eq $Project
        )

        Write-Host "TASK_FOUND=True"
        Write-Host "TASK_STATE=$($task.State)"
        Write-Host "RUN_AS=$($task.Principal.UserId)"
        Write-Host "LAST_RUN_TIME=$($info.LastRunTime)"
        Write-Host "LAST_TASK_RESULT=$($info.LastTaskResult)"
        Write-Host "NEXT_RUN_TIME=$($info.NextRunTime)"
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
    -Argument $BackupArguments `
    -WorkingDirectory $Project

$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At "23:00"

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 10) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
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
    -Description "Daily DELISKY production backup at 23:00." `
    -Force |
    Out-Null

Write-Host "TASK_INSTALLED=True"

if ($StartNow) {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "TASK_STARTED=True"
    Wait-BackupTask
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
$installedAction = @($task.Actions)[0]

$actionMatches = (
    $installedAction.Execute -eq $PowerShell -and
    $installedAction.Arguments -eq $BackupArguments -and
    $installedAction.WorkingDirectory -eq $Project
)

Write-Host "TASK_STATE=$($task.State)"
Write-Host "RUN_AS=$($task.Principal.UserId)"
Write-Host "LAST_RUN_TIME=$($info.LastRunTime)"
Write-Host "LAST_TASK_RESULT=$($info.LastTaskResult)"
Write-Host "NEXT_RUN_TIME=$($info.NextRunTime)"
Write-Host "ACTION_MATCHES_EXPECTED=$actionMatches"

if (-not $actionMatches) {
    throw "BACKUP_TASK_ACTION_MISMATCH"
}

if ($StartNow -and $info.LastTaskResult -ne 0) {
    throw "BACKUP_TASK_SMOKE_RUN_FAILED: $($info.LastTaskResult)"
}
