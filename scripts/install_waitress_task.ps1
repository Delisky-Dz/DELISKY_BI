param(
    [ValidateSet("Check", "Install")]
    [string]$Mode = "Check",

    [switch]$StartNow
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TaskName = "DELISKY Production Waitress"
$TaskPath = "\"
$Project = Split-Path $PSScriptRoot -Parent
$Launcher = Join-Path $PSScriptRoot "start_production_waitress.ps1"
$PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$LauncherArguments = (
    '-NoProfile -ExecutionPolicy Bypass -File "{0}"'
) -f $Launcher

function Test-TaskConfiguration {
    param($Task)
    $actions = @($Task.Actions)
    $triggers = @($Task.Triggers)
    return (
        $actions.Count -eq 1 -and
        $actions[0].Execute -eq $PowerShell -and
        $actions[0].Arguments -eq $LauncherArguments -and
        $actions[0].WorkingDirectory -eq $Project -and
        $Task.Principal.UserId -in @("SYSTEM", "S-1-5-18") -and
        $Task.Principal.LogonType -eq "ServiceAccount" -and
        $triggers.Count -eq 1 -and
        $triggers[0].CimClass.CimClassName -eq "MSFT_TaskBootTrigger" -and
        $triggers[0].Delay -eq "PT30S" -and
        $Task.Settings.Enabled -and
        $Task.Settings.StartWhenAvailable -and
        $Task.Settings.MultipleInstances -eq "IgnoreNew" -and
        $Task.Settings.RestartCount -eq 3 -and
        $Task.Settings.RestartInterval -eq "PT1M" -and
        $Task.Settings.ExecutionTimeLimit -eq "PT0S" -and
        -not $Task.Settings.DisallowStartIfOnBatteries -and
        -not $Task.Settings.StopIfGoingOnBatteries
    )
}

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

$configurationMatches = $false
$actionMatches = $false
if ($Mode -eq "Check") {
    try {
        $task = Get-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction Stop
        $info = Get-ScheduledTaskInfo -TaskPath $TaskPath -TaskName $TaskName -ErrorAction Stop
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
        $configurationMatches = Test-TaskConfiguration -Task $task
        Write-Host "CONFIGURATION_MATCHES_EXPECTED=$configurationMatches"
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

    if (-not $actionMatches -or -not $configurationMatches) { throw "WAITRESS_TASK_CHECK_FAILED" }
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
$trigger.Delay = "PT30S"

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskPath $TaskPath -TaskName $TaskName `
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
Write-Host "TASK_PATH=$TaskPath"
Write-Host "RESTART_POLICY=3 attempts at 1 minute"

if ($StartNow) {
    Start-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName
    Start-Sleep -Seconds 5
}

$task = Get-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskPath $TaskPath -TaskName $TaskName -ErrorAction Stop
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

if (-not $actionMatches -or -not (Test-TaskConfiguration -Task $task)) {
    throw "WAITRESS_TASK_CONFIGURATION_MISMATCH"
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
