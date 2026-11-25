param(
    [ValidateSet("Check", "Install")]
    [string]$Mode = "Check",
    [string]$TaskUser,
    [switch]$StartNow
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'production_waitress_task_definition.ps1')

function Get-AccountSid {
    param([string]$Name)
    if ($Name -match '^S-1-') { return $Name }
    return ([Security.Principal.NTAccount]$Name).Translate([Security.Principal.SecurityIdentifier]).Value
}

function Test-TaskConfiguration {
    param($Task)
    if (-not (Test-ManagedWaitressTask $Task)) { return $false }
    $triggers = @($Task.Triggers)
    $settings = $Task.Settings
    return (
        $Task.Principal.LogonType -eq 'S4U' -and
        $Task.Principal.RunLevel -eq 'Limited' -and
        (Get-AccountSid $Task.Principal.UserId) -eq $ExpectedSid -and
        $triggers.Count -eq 1 -and $triggers[0].Enabled -and
        $triggers[0].CimClass.CimClassName -eq 'MSFT_TaskBootTrigger' -and
        $triggers[0].Delay -eq 'PT30S' -and
        $settings.Enabled -and $settings.StartWhenAvailable -and
        $settings.MultipleInstances -eq 'IgnoreNew' -and
        $settings.RestartCount -eq 10 -and $settings.RestartInterval -eq 'PT1M' -and
        $settings.ExecutionTimeLimit -eq 'PT0S' -and
        -not $settings.DisallowStartIfOnBatteries -and -not $settings.StopIfGoingOnBatteries
    )
}

$task = Get-WaitressTask
if (-not $TaskUser) {
    if ($Mode -eq 'Install') { throw 'Supply -TaskUser COMPUTER\local-user for unattended operation.' }
    if (-not $task) { throw 'WAITRESS_TASK_NOT_FOUND' }
    $TaskUser = $task.Principal.UserId
}
$ExpectedSid = Get-AccountSid $TaskUser
# Resolve a real local user, excluding built-in Administrator and service identities.
$localUser = Get-LocalUser -SID ([Security.Principal.SecurityIdentifier]$ExpectedSid)
if (-not $localUser.Enabled -or $ExpectedSid -notlike 'S-1-5-21-*' -or $ExpectedSid -like '*-500') {
    throw 'An enabled local deployment or service user is required.'
}

if ($Mode -eq 'Install') {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'ADMINISTRATOR_PRIVILEGES_REQUIRED'
    }
    if ($task -and -not (Test-ManagedWaitressTask $task -AllowLegacy)) { throw 'TASK_NAME_COLLISION' }
    if (-not $task -or -not (Test-TaskConfiguration $task)) {
        if ($task -and $task.State -in @('Running', 'Queued')) { throw 'Stop the managed task before repairing it.' }
        $action = New-ScheduledTaskAction -Execute $PowerShell -Argument $LauncherArguments -WorkingDirectory $Project
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $trigger.Delay = 'PT30S'
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 10 `
            -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        $principal = New-ScheduledTaskPrincipal -UserId $ExpectedSid -LogonType S4U -RunLevel Limited
        $register = @{
            TaskPath = $TaskPath; TaskName = $TaskName; Action = $action; Trigger = $trigger
            Settings = $settings; Principal = $principal; Description = $TaskDescription
        }
        Register-ScheduledTask @register -Force:([bool]$task) | Out-Null
        $task = Get-WaitressTask
    }
}
if (-not $task -or -not (Test-TaskConfiguration $task)) { throw 'WAITRESS_TASK_CONFIGURATION_MISMATCH' }
Write-Host "TASK_NAME=$TaskName"
Write-Host "RUN_AS=$($localUser.Name) SID=$ExpectedSid S4U Limited"
Write-Host "ACTION=$PowerShell $LauncherArguments"
Write-Host "PROJECT=$Project"
Write-Host 'STARTUP=Boot + 30 seconds'
Write-Host 'RESTART_POLICY=10 retries at 1 minute'
Write-Host "MULTIPLE_INSTANCES=$($task.Settings.MultipleInstances)"
Write-Host "ENABLED=$($task.Settings.Enabled)"
if ($StartNow) {
    if ($Mode -ne 'Install') { throw 'StartNow requires Install mode.' }
    Start-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName
}
$info = Get-ScheduledTaskInfo -TaskPath $TaskPath -TaskName $TaskName
Write-Host "TASK_STATE=$((Get-WaitressTask).State)"
Write-Host "LAST_RUN_TIME=$($info.LastRunTime)"
Write-Host "LAST_TASK_RESULT=$($info.LastTaskResult)"
Write-Host 'CONFIGURATION_MATCHES_EXPECTED=True'
