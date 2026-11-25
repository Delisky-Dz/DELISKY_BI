# Shared identity for the installer, read-only inspection and rollback.
$TaskName = 'DELISKY Production Waitress'
$TaskPath = '\'
$Project = Split-Path $PSScriptRoot -Parent
$Launcher = Join-Path $PSScriptRoot 'start_production_waitress.ps1'
$PowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$LauncherArguments = '-NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File "{0}"' -f $Launcher
$TaskDescription = 'DELISKY BI managed production Waitress task (v2).'

function Get-WaitressTask {
    # Enumerate the root so an access error cannot be mistaken for a missing task.
    Get-ScheduledTask -TaskPath $TaskPath -ErrorAction Stop |
        Where-Object { $_.TaskName -eq $TaskName }
}

function Test-ManagedWaitressTask {
    param($Task, [switch]$AllowLegacy)
    if (@($Task.Actions).Count -ne 1) { return $false }
    $action = $Task.Actions[0]
    if ($action.Execute -ne $PowerShell -or $action.WorkingDirectory -ne $Project) { return $false }
    if ($Task.Description -ceq $TaskDescription -and $action.Arguments -eq $LauncherArguments) { return $true }

    $legacyArguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $Launcher
    $legacyDescription = 'Starts DELISKY Production Waitress only after branch, working-tree, origin/main, static-manifest and Django safety checks pass.'
    return ($AllowLegacy -and $Task.Description -ceq $legacyDescription -and $action.Arguments -eq $legacyArguments)
}
