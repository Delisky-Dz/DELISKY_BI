# DELISKY BI Production Waitress recovery

The operator observed that the launcher passed its Git, database-selection, static and Django guards, then Windows Application Control blocked the generated Waitress executable. Starting the installed Waitress module with the project Python restored the listener and the public redirect to /login/. Cloudflared already reached the correct origin.

During PR #18 acceptance, the site remained reachable after Windows logout. In the crash drill the child was terminated, the launcher logged exit code -1 and ended, the task returned to Ready with result 4294967295, and port 8080 stayed empty despite the registered RestartOnFailure policy. A manual task start restored service. The cause of Scheduler skipping the retry was not established.

## Runtime

The root-folder task DELISKY Production Waitress starts 30 seconds after boot. Its attached Windows PowerShell 5.1 action sets the working directory, checks clean main against the local origin/main reference, forces production settings and database delisky_bi, verifies the static manifest, runs Django check, and checks port 8080. It then waits for this foreground command:

~~~powershell
& "$project\.venv\Scripts\python.exe" -m waitress --listen=127.0.0.1:8080 --threads=4 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-proto config.wsgi:application
~~~

Task Scheduler starts one foreground PowerShell supervisor. The supervisor validates Git, settings, static assets and Django once. On **every** launch it checks the loopback endpoint and conflicting wildcard listeners, starts the project interpreter directly, and waits on the process handle. The task has no execution time limit. A deliberate task stop ends the task process tree and its recovery loop. During manual maintenance stop the task itself.

After any unexpected child exit (including zero), the same supervisor waits 15 seconds and starts the child again. There are at most ten consecutive retries after the initial launch. A child runtime of at least 300 seconds resets that budget. Runtime is measured with a monotonic clock. An occupied endpoint, an infrastructure exception or an exhausted budget ends the launcher with code 1 and a fatal reason. No competing listener is terminated. Task Scheduler retains ten retries at one-minute intervals as a secondary layer for launcher failure. If the task stays Ready after exhausting recovery, inspect the transcript before starting it again.

The transcript records the supervisor PID, child start and exit times, the direct venv child PID, exit code, runtime, retry number and delay. On Windows the venv redirector may spawn the worker that owns the socket. Use the listener PID and its ancestry for a crash drill. A child start log confirms process creation. The health check confirms HTTP recovery.

Cloudflare Tunnel continues to use 127.0.0.1:8080. Deployment performs Git synchronization separately. The launcher performs no migration or static collection.

The installer requires an explicitly selected, enabled local Windows account, uses S4U and requests limited privileges. The task can run after logout without storing the user's password. The old installer selected SYSTEM, whose access to this user-owned checkout and settings was unverified. Prefer a local deployment account that already owns or is trusted for this specific checkout. The account needs batch logon under existing policy, access to the Git executable and refs, read/execute access to the venv and its base interpreter, read access to settings, .env and static files, and write access to logs and any application upload destinations. Use local unencrypted resources accessible without interactive profile initialization. PostgreSQL must accept the application's configured credentials over loopback. Do not place credentials in commands. Validate actual access by logging into the application and reading an existing database-backed page during acceptance.

## Manual Production acceptance

Start from the healthy PR #18 deployment at aebdf1d7a33242659ec330b4c698d83a61542752. Run one command at a time in an elevated 64-bit Windows PowerShell 5.1 maintenance session. Stop at any failed check. Use the merged SHA in the implementation report.

1. Set the session variables and check the baseline. From a second device, confirm that you can open the application.

~~~powershell
$project = 'C:\Users\Delisky Self-host\DELISKY_BI'
$task = 'DELISKY Production Waitress'
$ps51 = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$log = Join-Path $project 'logs\production-waitress.log'
Set-Location -LiteralPath $project
& $ps51 -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\check_production_health.ps1 -Public
if ($LASTEXITCODE) { throw 'Baseline health failed' }
if ((git rev-parse HEAD) -ne 'aebdf1d7a33242659ec330b4c698d83a61542752') { throw 'Review unexpected starting commit' }
~~~

2. Confirm clean main, fetch, fast-forward to the approved merge and verify the deployed SHA. If remote main has advanced further, review the new changes before deploying.

~~~powershell
if ((git branch --show-current) -ne 'main' -or (git status --porcelain) -or $LASTEXITCODE) { throw 'Expected clean main' }
$approved = (Read-Host 'Approved full merge SHA').Trim()
git fetch origin main
if ($LASTEXITCODE -or $approved -notmatch '^[0-9a-f]{40}$' -or (git rev-parse refs/remotes/origin/main) -ne $approved) { throw 'Review remote main' }
git merge --ff-only $approved
if ($LASTEXITCODE -or (git rev-parse HEAD) -ne $approved -or (git status --porcelain)) { throw 'Deployment verification failed' }
git log -1 --format='%H %s'
~~~

3. Confirm the identity of the **existing running managed task**, then stop it. Wait for both the task and listener to stop. A remaining listener requires inspection before proceeding.

~~~powershell
$expectedLauncher = Join-Path $project 'scripts\start_production_waitress.ps1'
$expectedArgs = '-NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File "{0}"' -f $expectedLauncher
$t = Get-ScheduledTask -TaskPath '\' -TaskName $task -ErrorAction Stop
if ($t.State -ne 'Running' -or $t.Description -ne 'DELISKY BI managed production Waitress task (v2).' -or @($t.Actions).Count -ne 1 -or $t.Actions[0].Execute -ne $ps51 -or $t.Actions[0].WorkingDirectory -ne $project -or $t.Actions[0].Arguments -ne $expectedArgs) { throw 'Unexpected task; inspect before stopping' }
Stop-ScheduledTask -TaskPath '\' -TaskName $task -ErrorAction Stop
$deadline = (Get-Date).AddSeconds(45)
do { $running = (Get-ScheduledTask -TaskPath '\' -TaskName $task).State -in @('Running','Queued'); $onPort = @([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object Port -eq 8080); if ($running -or $onPort.Count) { Start-Sleep -Seconds 1 } } while (($running -or $onPort.Count) -and (Get-Date) -lt $deadline)
if ($running -or $onPort.Count) { throw 'Task or listener still active' }
~~~

4. This release changes only the supervised launcher at the registered path. **Skip task installation and repair.** Start the task once to load the new launcher. Allow time for the startup guards. Check health, then open an existing database-backed page from a second device.

~~~powershell
Start-ScheduledTask -TaskPath '\' -TaskName $task -ErrorAction Stop
Get-Content -LiteralPath $log -Tail 35
& $ps51 -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\check_production_health.ps1 -Public
if ($LASTEXITCODE) { throw 'Wait for initial startup or inspect the log before the drill' }
~~~

5. In the same session, identify the current listener, pin its process handle, and match its ancestry to the supervisor PID in the latest transcript. Capture the task run time. If ownership cannot be proved, stop the drill.

~~~powershell
$rows = @(Get-NetTCPConnection -State Listen -LocalPort 8080 -ErrorAction Stop)
if ($rows.Count -ne 1 -or $rows[0].LocalAddress -ne '127.0.0.1') { throw 'Listener mismatch' }
$target = Get-Process -Id $rows[0].OwningProcess -ErrorAction Stop
$null = $target.Handle
$server = Get-CimInstance Win32_Process -Filter "ProcessId=$($target.Id)" -ErrorAction Stop
$expectedPython = Join-Path $project '.venv\Scripts\python.exe'
$pidRecord = Select-String -LiteralPath $log -Pattern '^SUPERVISOR_PID=(\d+)' | Select-Object -Last 1
if (-not $pidRecord) { throw 'New supervisor log missing' }
$supervisorId = [int]$pidRecord.Matches[0].Groups[1].Value
$taskRun = (Get-ScheduledTaskInfo -TaskName $task -TaskPath '\').LastRunTime
$node = $server
$venvSeen = $false
$launcherSeen = $false
for ($i=0; $node -and $i -lt 5; $i++) {
    if ($node.ExecutablePath -eq $expectedPython) { $venvSeen = $true }
    if ($node.ProcessId -eq $supervisorId -and $node.ExecutablePath -eq $ps51 -and $node.CommandLine.EndsWith($expectedArgs, [StringComparison]::OrdinalIgnoreCase)) { $launcherSeen = $true; break }
    $node = Get-CimInstance Win32_Process -Filter "ProcessId=$($node.ParentProcessId)"
}
$verified = $venvSeen -and $launcherSeen -and $server.Name -eq 'python.exe' -and $server.CommandLine -match '(?:^|\s)-m\s+waitress\s' -and $server.CommandLine.Contains('--listen=127.0.0.1:8080') -and $server.CommandLine.Contains('config.wsgi:application')
if (-not $verified -or (Get-ScheduledTask -TaskPath '\' -TaskName $task).State -ne 'Running') { throw 'Waitress ancestry not confirmed' }
$target | Select-Object Id,ProcessName,StartTime
~~~

6. Terminate **only the verified Waitress child**. Use its pinned process handle. **Do not call Start-ScheduledTask after this point.** Wait for a different listener PID to appear automatically. The internal delay is 15 seconds; allow up to 90 seconds for the new worker to bind and initialize.

~~~powershell
if ($verified -and -not $target.HasExited) { $target.Kill() } else { throw 'Child identity changed' }
$deadline = (Get-Date).AddSeconds(90)
do { Start-Sleep -Seconds 2; $newRows = @(Get-NetTCPConnection -State Listen -LocalPort 8080 -ErrorAction SilentlyContinue) } until (($newRows.Count -eq 1 -and $newRows[0].OwningProcess -ne $target.Id) -or (Get-Date) -ge $deadline)
if ($newRows.Count -ne 1 -or $newRows[0].LocalAddress -ne '127.0.0.1' -or $newRows[0].OwningProcess -eq $target.Id) { throw 'Automatic child recovery failed' }
$newRows | Select-Object LocalAddress,LocalPort,OwningProcess
Get-Content -LiteralPath $log -Tail 40
& $ps51 -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\check_production_health.ps1 -Public
if ($LASTEXITCODE) { throw 'Post-recovery HTTP, listener or Git check failed' }
if ((Get-ScheduledTask -TaskPath '\' -TaskName $task).State -ne 'Running' -or (Get-ScheduledTaskInfo -TaskName $task -TaskPath '\').LastRunTime -ne $taskRun) { throw 'Original task instance did not stay running' }
~~~

Record the old and new listener PIDs, exit and replacement timestamps, recovery attempt, delay, and PASS statuses. Verify the public database-backed page from a second device. **Crash recovery passes only if a new Waitress PID appears automatically after the verified child dies, without a manual task start.** If recovery fails, preserve evidence before using the maintenance/emergency procedure.

7. Sign out of the Windows operator session. From a second device, refresh the application and open the same page. After signing back in, repeat the session variable assignments in step 1 and run the health check.

8. During an approved maintenance window restart Windows normally. Confirm public access from a second device **before** any Windows login. After login, set the session variables again and record the boot, task, listener and HTTP evidence.

~~~powershell
(Get-CimInstance Win32_OperatingSystem).LastBootUpTime
Get-ScheduledTask -TaskPath '\' -TaskName $task | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskPath '\' -TaskName $task | Select-Object LastRunTime,LastTaskResult
Get-Content -LiteralPath $log -Tail 35
& $ps51 -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\check_production_health.ps1 -Public
~~~

## Logs, emergency launch and rollback

The launcher appends to logs\production-waitress.log and rotates the previous transcript to .log.1 at startup or between retries when the current log exceeds 10 MiB. Both are ignored by Git. Look for start and stop timestamps, guard results, exit code and fatal reason. If execution fails before the transcript opens, inspect Task Scheduler's result and its Operational history when available.

Before performing rollback, run the installer's Check command and confirm the action points to this checkout. Disable and stop that managed task for maintenance. Verify 8080 is free using step 3.

~~~powershell
Disable-ScheduledTask -TaskPath '\' -TaskName $task
Stop-ScheduledTask -TaskPath '\' -TaskName $task
& $ps51 -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\uninstall_production_waitress_task.ps1 -WhatIf
& $ps51 -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\uninstall_production_waitress_task.ps1
~~~

Start the guarded launcher in a foreground console if service is needed immediately. This is the emergency command for the Python module invocation shown above. Keep the console open until the supervised task takes over. The uninstaller preserves application files, data and logs.

~~~powershell
& $ps51 -NoProfile -ExecutionPolicy RemoteSigned -File "$project\scripts\start_production_waitress.ps1"
~~~
