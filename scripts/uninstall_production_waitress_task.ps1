[CmdletBinding(SupportsShouldProcess)]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'production_waitress_task_definition.ps1')
$task = Get-WaitressTask
if (-not $task) { Write-Host 'TASK_ALREADY_ABSENT=True'; return }
if (-not (Test-ManagedWaitressTask $task)) { throw 'TASK_OWNERSHIP_MISMATCH' }
if ($task.State -in @('Running', 'Queued')) { throw 'Stop the managed task before removing it.' }
if ($PSCmdlet.ShouldProcess("$TaskPath$TaskName", 'Unregister managed Waitress task')) {
    Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Confirm:$false -ErrorAction Stop
    Write-Host 'TASK_REMOVED=True'
}
