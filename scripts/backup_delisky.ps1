param(
    [string]$DjangoSettings = "config.settings.development"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = "C:\Users\MediaNet\DELISKY_BI"

$backupRoot = "H:\DELISKY_BACKUPS"
$dbBackupRoot = Join-Path $backupRoot "PostgreSQL"
$projectBackupRoot = Join-Path $backupRoot "Project"
$mediaBackupRoot = Join-Path $backupRoot "Media"
$logRoot = Join-Path $backupRoot "Logs"

$expectedDiskSerial = "WD-WXH1EA64AK1P"

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonHelper = Join-Path $projectRoot "scripts\backup_database.py"
$workingTreeHelper = Join-Path $projectRoot "scripts\backup_working_tree.py"

$pgDump = "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
$pgRestore = "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe"

$today = Get-Date -Format "yyyy-MM-dd"
$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"

$dbDayDir = Join-Path $dbBackupRoot $today
$projectDayDir = Join-Path $projectBackupRoot $today
$mediaDayDir = Join-Path $mediaBackupRoot $today

$logFile = $null

function Write-BackupLog {
    param([string]$Message)

    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message

    Write-Host $line

    if ($null -ne $logFile) {
        Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
    }
}

try {
    foreach ($requiredFile in @(
        $python,
        $pythonHelper,
        $workingTreeHelper,
        $pgDump,
        $pgRestore
    )) {
        if (-not (Test-Path -LiteralPath $requiredFile)) {
            throw "Required file not found: $requiredFile"
        }
    }

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git executable was not found."
    }

    # Verify dedicated backup disk.
    $partition = Get-Partition -DriveLetter H -ErrorAction Stop
    $disk = Get-Disk -Number $partition.DiskNumber -ErrorAction Stop
    $volume = Get-Volume -DriveLetter H -ErrorAction Stop

    if ($disk.SerialNumber.Trim() -ne $expectedDiskSerial) {
        throw "H: is not the expected DELISKY backup disk."
    }

    if ($disk.HealthStatus -ne "Healthy") {
        throw "DELISKY backup disk health is not Healthy."
    }

    if ($volume.HealthStatus -ne "Healthy") {
        throw "DELISKY backup volume health is not Healthy."
    }

    # Prepare directories.
    New-Item -ItemType Directory -Path $dbDayDir -Force | Out-Null
    New-Item -ItemType Directory -Path $projectDayDir -Force | Out-Null
    New-Item -ItemType Directory -Path $mediaDayDir -Force | Out-Null
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

    $logFile = Join-Path $logRoot "backup_$today.log"

    Write-BackupLog "============================================================"
    Write-BackupLog "DELISKY backup started."
    Write-BackupLog "Backup disk: $($disk.FriendlyName)"
    Write-BackupLog "Backup disk serial verified: $expectedDiskSerial"

    # ---------------------------------------------------------------
    # PostgreSQL
    # ---------------------------------------------------------------

    $dbBackupFile = Join-Path $dbDayDir "delisky_bi_$timestamp.dump"

    $env:DELISKY_BACKUP_DJANGO_SETTINGS = $DjangoSettings

    Push-Location $projectRoot

    try {
        & $python $pythonHelper `
            --output $dbBackupFile `
            --pg-dump $pgDump

        if ($LASTEXITCODE -ne 0) {
            throw "PostgreSQL backup helper failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
        Remove-Item Env:DELISKY_BACKUP_DJANGO_SETTINGS -ErrorAction SilentlyContinue
    }

    if (-not (Test-Path -LiteralPath $dbBackupFile)) {
        throw "Database backup file was not created."
    }

    if ((Get-Item -LiteralPath $dbBackupFile).Length -le 0) {
        throw "Database backup file is empty."
    }

    Write-BackupLog "PostgreSQL dump created: $dbBackupFile"

    & $pgRestore --list $dbBackupFile | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL archive verification failed."
    }

    Write-BackupLog "PostgreSQL archive verification passed."

    $dbHash = Get-FileHash -LiteralPath $dbBackupFile -Algorithm SHA256

    "$($dbHash.Hash) *$([System.IO.Path]::GetFileName($dbBackupFile))" |
        Set-Content `
            -LiteralPath "$dbBackupFile.sha256" `
            -Encoding ASCII

    Write-BackupLog "PostgreSQL SHA-256: $($dbHash.Hash)"

    # ---------------------------------------------------------------
    # Git repository
    # ---------------------------------------------------------------

    $gitBundle = Join-Path `
        $projectDayDir `
        "DELISKY_BI_$timestamp.bundle"

    & git -C $projectRoot bundle create $gitBundle --all

    if ($LASTEXITCODE -ne 0) {
        throw "Git bundle creation failed."
    }

    & git -C $projectRoot bundle verify $gitBundle | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "Git bundle verification failed."
    }

    $gitHash = Get-FileHash `
        -LiteralPath $gitBundle `
        -Algorithm SHA256

    "$($gitHash.Hash) *$([System.IO.Path]::GetFileName($gitBundle))" |
        Set-Content `
            -LiteralPath "$gitBundle.sha256" `
            -Encoding ASCII

    Write-BackupLog "Git bundle created and verified: $gitBundle"
    Write-BackupLog "Git bundle SHA-256: $($gitHash.Hash)"

    # Working-tree snapshot:
    # tracked files plus untracked, non-ignored files.
    # Ignored secrets and local data are not included.
    $workingTreeArchive = Join-Path `
        $projectDayDir `
        "DELISKY_BI_working_tree_$timestamp.zip"

    & $python $workingTreeHelper `
        --output $workingTreeArchive

    if ($LASTEXITCODE -ne 0) {
        throw "Working-tree snapshot failed with exit code $LASTEXITCODE."
    }

    if (-not (Test-Path -LiteralPath $workingTreeArchive)) {
        throw "Working-tree snapshot was not created."
    }

    $workingTreeHash = Get-FileHash `
        -LiteralPath $workingTreeArchive `
        -Algorithm SHA256

    "$($workingTreeHash.Hash) *$([System.IO.Path]::GetFileName($workingTreeArchive))" |
        Set-Content `
            -LiteralPath "$workingTreeArchive.sha256" `
            -Encoding ASCII

    Write-BackupLog "Working-tree snapshot created: $workingTreeArchive"
    Write-BackupLog "Working-tree SHA-256: $($workingTreeHash.Hash)"

    $gitStatus = & git -C $projectRoot status --porcelain

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read Git working tree status."
    }

    if ($gitStatus) {
        Write-BackupLog "WARNING: Git working tree contains uncommitted changes."
    }
    else {
        Write-BackupLog "Git working tree is clean."
    }

    # ---------------------------------------------------------------
    # Media
    # ---------------------------------------------------------------

    $mediaSource = Join-Path $projectRoot "media"

    if (Test-Path -LiteralPath $mediaSource) {
        $mediaItems = @(
            Get-ChildItem -LiteralPath $mediaSource -Force
        )

        if ($mediaItems.Count -gt 0) {
            $mediaArchive = Join-Path `
                $mediaDayDir `
                "media_$timestamp.zip"

            Compress-Archive `
                -Path (Join-Path $mediaSource "*") `
                -DestinationPath $mediaArchive `
                -CompressionLevel Optimal `
                -Force

            if (-not (Test-Path -LiteralPath $mediaArchive)) {
                throw "Media archive was not created."
            }

            $mediaHash = Get-FileHash `
                -LiteralPath $mediaArchive `
                -Algorithm SHA256

            "$($mediaHash.Hash) *$([System.IO.Path]::GetFileName($mediaArchive))" |
                Set-Content `
                    -LiteralPath "$mediaArchive.sha256" `
                    -Encoding ASCII

            Write-BackupLog "Media archive created: $mediaArchive"
            Write-BackupLog "Media SHA-256: $($mediaHash.Hash)"
        }
        else {
            Write-BackupLog "Media directory is empty; backup skipped."
        }
    }
    else {
        Write-BackupLog "Media directory does not exist; backup skipped."
    }

    # ---------------------------------------------------------------
    # Encrypted secrets backup
    # ---------------------------------------------------------------

    $envSource = Join-Path $projectRoot ".env"
    $recipientFile = Join-Path `
        $projectRoot `
        "config\backup_age_recipient.txt"

    if (-not (Test-Path -LiteralPath $envSource)) {
        throw "Required .env file was not found."
    }

    if (-not (Test-Path -LiteralPath $recipientFile)) {
        throw "Age recipient file was not found."
    }

    $recipient = (
        Get-Content `
            -LiteralPath $recipientFile `
            -Raw
    ).Trim()

    if ($recipient -notmatch '^age1[0-9a-z]+$') {
        throw "Age recipient file contains an invalid recipient."
    }

    $ageCommand = Get-Command `
        age.exe `
        -ErrorAction SilentlyContinue

    if ($null -ne $ageCommand) {
        $ageExe = $ageCommand.Source
    }
    else {
        $ageExe = Get-ChildItem `
            -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" `
            -Filter "age.exe" `
            -File `
            -Recurse `
            -ErrorAction SilentlyContinue |
            Where-Object {
                $_.FullName -match 'FiloSottile\.age'
            } |
            Select-Object -First 1 -ExpandProperty FullName
    }

    if (-not $ageExe -or -not (Test-Path -LiteralPath $ageExe)) {
        throw "age.exe was not found."
    }

    $secretsDate = Get-Date -Format "yyyy-MM-dd"

    $secretsDayDir = Join-Path `
        (Join-Path $backupRoot "Secrets") `
        $secretsDate

    New-Item `
        -ItemType Directory `
        -Path $secretsDayDir `
        -Force |
        Out-Null

    $encryptedEnv = Join-Path `
        $secretsDayDir `
        "DELISKY_env_$timestamp.age"

    $encryptedEnvPartial = "$encryptedEnv.partial"

    Remove-Item `
        -LiteralPath $encryptedEnvPartial `
        -Force `
        -ErrorAction SilentlyContinue

    & $ageExe `
        -r $recipient `
        -o $encryptedEnvPartial `
        $envSource

    if ($LASTEXITCODE -ne 0) {
        Remove-Item `
            -LiteralPath $encryptedEnvPartial `
            -Force `
            -ErrorAction SilentlyContinue

        throw "Encrypted .env backup failed."
    }

    if (
        -not (Test-Path -LiteralPath $encryptedEnvPartial) -or
        (Get-Item -LiteralPath $encryptedEnvPartial).Length -le 0
    ) {
        throw "Encrypted .env backup was not created correctly."
    }

    Move-Item `
        -LiteralPath $encryptedEnvPartial `
        -Destination $encryptedEnv `
        -Force

    $encryptedEnvHash = Get-FileHash `
        -LiteralPath $encryptedEnv `
        -Algorithm SHA256

    "$($encryptedEnvHash.Hash) *$([System.IO.Path]::GetFileName($encryptedEnv))" |
        Set-Content `
            -LiteralPath "$encryptedEnv.sha256" `
            -Encoding ASCII

    Write-BackupLog "Encrypted .env backup created: $encryptedEnv"
    Write-BackupLog "Encrypted .env SHA-256: $($encryptedEnvHash.Hash)"
    # ---------------------------------------------------------------
    # Retention policy
    # ---------------------------------------------------------------

    $retentionHelper = Join-Path `
        $projectRoot `
        "scripts\backup_retention.py"

    if (-not (Test-Path -LiteralPath $retentionHelper)) {
        throw "Retention helper not found: $retentionHelper"
    }

    $retentionOutput = @(
        & $python $retentionHelper `
            --backup-root $backupRoot `
            --keep-all-days 30 `
            --keep-weekly-weeks 12 `
            --keep-monthly-months 12 `
            --minimum-protected-days 14 `
            --emergency-free-gb 50 `
            --emergency-target-gb 75 `
            --apply 2>&1
    )

    $retentionExitCode = $LASTEXITCODE

    foreach ($line in $retentionOutput) {
        Write-BackupLog "Retention: $line"
    }

    if ($retentionExitCode -ne 0) {
        throw "Retention policy failed with exit code $retentionExitCode."
    }

    if (-not ($retentionOutput -contains "RETENTION_RESULT=PASS")) {
        throw "Retention policy did not report PASS."
    }
    # ---------------------------------------------------------------
    # Capacity
    # ---------------------------------------------------------------

    $volumeAfter = Get-Volume -DriveLetter H

    $freeGB = [math]::Round(
        $volumeAfter.SizeRemaining / 1GB,
        2
    )

    $totalGB = [math]::Round(
        $volumeAfter.Size / 1GB,
        2
    )

    Write-BackupLog "Backup disk free space: $freeGB GB / $totalGB GB"
    Write-BackupLog "DELISKY backup completed successfully."
    Write-BackupLog "============================================================"

    exit 0
}
catch {
    $message = $_.Exception.Message

    Write-Host "DELISKY BACKUP FAILED: $message" -ForegroundColor Red

    if ($null -ne $logFile) {
        Add-Content `
            -LiteralPath $logFile `
            -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  FAILED: $message" `
            -Encoding UTF8
    }

    exit 1
}
