Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Project = Split-Path $PSScriptRoot -Parent
$Python = Join-Path $Project ".venv\Scripts\python.exe"
$PgRestore = "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe"
$BackupRoot = "D:\DELISKY_BACKUPS\PostgreSQL"
$WaitressCheck = Join-Path $PSScriptRoot "install_waitress_task.ps1"
$BackupCheck = Join-Path $PSScriptRoot "install_backup_task.ps1"

function Write-Section {
    param([string]$Name)

    Write-Host ""
    Write-Host "=== $Name ==="
}

Write-Host "=== DELISKY PRODUCTION HOST READ-ONLY STATUS ==="
Write-Host "PROJECT=$Project"

Write-Section "GIT"

$currentBranch = (& git -C $Project branch --show-current).Trim()
$head = (& git -C $Project rev-parse HEAD).Trim()
$originMain = (& git -C $Project rev-parse refs/remotes/origin/main).Trim()
$workingTree = @(& git -C $Project status --porcelain)

Write-Host "BRANCH=$currentBranch"
Write-Host "HEAD=$head"
Write-Host "ORIGIN_MAIN=$originMain"
Write-Host "WORKING_TREE_CLEAN=$($workingTree.Count -eq 0)"
Write-Host "HEAD_MATCHES_ORIGIN_MAIN=$($head -eq $originMain)"

if ($workingTree.Count -gt 0) {
    Write-Host "WORKING_TREE_CHANGES:"
    $workingTree | ForEach-Object {
        Write-Host "  $_"
    }
}

Write-Section "PRODUCTION SETTINGS"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "PRODUCTION_SETTINGS_CHECK=FAIL"
    Write-Host "PYTHON_NOT_FOUND=$Python"
}
else {
    $settingsOutput = @(
        & $Python -c (
            "import os; " +
            "os.environ['DJANGO_SETTINGS_MODULE']='config.settings.production'; " +
            "import django; django.setup(); " +
            "from django.conf import settings; " +
            "print('PRODUCTION_DATABASE=' + str(settings.DATABASES['default']['NAME']))"
        ) 2>&1
    )
    $settingsExitCode = $LASTEXITCODE

    $settingsOutput | ForEach-Object {
        Write-Host $_
    }

    Write-Host "PRODUCTION_SETTINGS_EXIT=$settingsExitCode"
}

Write-Section "WAITRESS TASK"

& $WaitressCheck -Mode Check

Write-Section "PORT 8080"

$listener = @(
    Get-NetTCPConnection `
        -LocalPort 8080 `
        -State Listen `
        -ErrorAction SilentlyContinue
)

Write-Host "PORT_8080_LISTENING=$($listener.Count -gt 0)"

foreach ($item in $listener) {
    Write-Host (
        "LISTENER={0}:{1} PID={2}" -f
        $item.LocalAddress,
        $item.LocalPort,
        $item.OwningProcess
    )
}

Write-Section "CLOUDFLARED"

$cloudflared = Get-Service `
    -Name "cloudflared" `
    -ErrorAction SilentlyContinue

if ($null -eq $cloudflared) {
    Write-Host "CLOUDFLARED_FOUND=False"
}
else {
    Write-Host "CLOUDFLARED_FOUND=True"
    Write-Host "CLOUDFLARED_STATUS=$($cloudflared.Status)"
}

Write-Section "BACKUP TASK"

& $BackupCheck -Mode Check

Write-Section "LATEST PRODUCTION BACKUP"

if (-not (Test-Path -LiteralPath $BackupRoot)) {
    Write-Host "BACKUP_ROOT_FOUND=False"
}
else {
    Write-Host "BACKUP_ROOT_FOUND=True"

    $latestBackup = Get-ChildItem `
        -LiteralPath $BackupRoot `
        -Recurse `
        -File `
        -Filter "delisky_bi_*.dump" `
        -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -notlike "delisky_bi_dev_*"
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -eq $latestBackup) {
        Write-Host "LATEST_PRODUCTION_BACKUP_FOUND=False"
    }
    else {
        Write-Host "LATEST_PRODUCTION_BACKUP_FOUND=True"
        Write-Host "BACKUP_FILE=$($latestBackup.FullName)"
        Write-Host "BACKUP_SIZE=$($latestBackup.Length)"
        Write-Host "BACKUP_TIME=$($latestBackup.LastWriteTime.ToString('s'))"

        if (Test-Path -LiteralPath $PgRestore) {
            $archiveHeader = @(
                & $PgRestore --list $latestBackup.FullName |
                Select-Object -First 12
            )

            $databaseLine = $archiveHeader |
                Where-Object {
                    $_ -match "^;\s+dbname:"
                } |
                Select-Object -First 1

            if ($null -ne $databaseLine) {
                Write-Host (
                    "BACKUP_ARCHIVE_" +
                    $databaseLine.TrimStart(";").Trim()
                )
            }
            else {
                Write-Host "BACKUP_ARCHIVE_DB=UNKNOWN"
            }
        }
        else {
            Write-Host "PG_RESTORE_FOUND=False"
        }
    }
}

Write-Host ""
Write-Host "READ_ONLY_STATUS_COMPLETE=True"
