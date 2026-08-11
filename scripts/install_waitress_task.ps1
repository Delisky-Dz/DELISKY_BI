param(
    [ValidateSet("Check", "Install")]
    [string]$Mode = "Check",

    [switch]$StartNow
)

$ErrorActionPreference = "Stop"

$TaskName = "DELISKY Production Waitress"
$Project = Split-Path $PSScriptRoot -Parent
$Waitress = Join-Path $Project ".venv\Scripts\waitress-serve.exe"

$WaitressArgs = "--listen=127.0.0.1:8080 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-proto config.wsgi:application"

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
Write-Host "WAITRESS_EXISTS=$(Test-Path $Waitress)"

if (-not (Test-Path $Waitress)) {
    throw "WAITRESS_NOT_FOUND: $Waitress"
}

if ($Mode -eq "Check") {
    try {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop

        Write-Host "TASK_FOUND=True"
        Write-Host "TASK_STATE=$($task.State)"
        Write-Host "LAST_RUN_TIME=$($info.LastRunTime)"
        Write-Host "LAST_TASK_RESULT=$($info.LastTaskResult)"
    }
    catch {
        Write-Host "TASK_FOUND=False"
        Write-Host "Run this script from an Administrator PowerShell for full task visibility."
    }

    exit 0
}

if (-not (Test-IsAdministrator)) {
    throw "ADMINISTRATOR_PRIVILEGES_REQUIRED"
}

$action = New-ScheduledTaskAction `
    -Execute $Waitress `
    -Argument $WaitressArgs `
    -WorkingDirectory $Project

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
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
    -Description "Runs DELISKY BI production Waitress on 127.0.0.1:8080 at Windows startup." `
    -Force | Out-Null

if ($StartNow) {
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 3
}

$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName

Write-Host "TASK_INSTALLED=True"
Write-Host "TASK_STATE=$($task.State)"
Write-Host "LAST_RUN_TIME=$($info.LastRunTime)"
Write-Host "LAST_TASK_RESULT=$($info.LastTaskResult)"
