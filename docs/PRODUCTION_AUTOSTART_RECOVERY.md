# DELISKY BI Production Waitress recovery

The operator observed that the launcher passed its Git, database-selection, static and Django guards, then Windows Application Control blocked the generated Waitress executable. Starting the installed Waitress module with the project Python restored the listener and the public redirect to /login/. Cloudflared already reached the correct origin.

## Runtime

The root-folder task DELISKY Production Waitress starts 30 seconds after boot. Its attached Windows PowerShell 5.1 action sets the working directory, checks clean main against the local origin/main reference, forces production settings and database delisky_bi, verifies the static manifest, runs Django check, and checks port 8080. It then waits for this foreground command:

~~~powershell
& "$project\.venv\Scripts\python.exe" -m waitress --listen=127.0.0.1:8080 --threads=4 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-proto config.wsgi:application
~~~

Cloudflare Tunnel connects to this loopback listener. The launcher performs no Git synchronization, migration or static collection. IgnoreNew suppresses duplicate task launches. An occupied port causes a logged failure and the OS bind result handles races. A nonzero child exit is propagated. An unsolicited zero exit is logged and translated to task failure. Scheduler retries up to ten times at one-minute intervals, starts when available, allows battery power and has no execution time limit. After the retry budget is exhausted, correct the logged cause and start the task.

The installer requires an explicitly selected, enabled local Windows account, uses S4U and requests limited privileges. The task can run after logout without storing the user's password. The old installer selected SYSTEM, whose access to this user-owned checkout and settings was unverified. Prefer a local deployment account that already owns or is trusted for this specific checkout. The account needs batch logon under existing policy, access to the Git executable and refs, read/execute access to the venv and its base interpreter, read access to settings, .env and static files, and write access to logs and any application upload destinations. Use local unencrypted resources accessible without interactive profile initialization. PostgreSQL must accept the application's configured credentials over loopback. Do not place credentials in commands. Validate actual access by logging into the application and reading an existing database-backed page during acceptance.

## Manual Production acceptance

Run commands one at a time in **elevated 64-bit Windows PowerShell 5.1** during a maintenance window. Record the merge SHA from the PR. Stop at any unexpected result. Before interrupting service, identify the console that owns the temporary foreground Waitress instance, and have the guarded emergency-launch command below ready in a second console.

1. Set the session variables. Use the known local deployment user. The example selects the account running this console. If elevated under a different account, specify the intended local account explicitly.

~~~powershell
$project = 'C:\Users\Delisky Self-host\DELISKY_BI'
$task = 'DELISKY Production Waitress'
$ps51 = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$taskUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
Set-Location -LiteralPath $project
~~~

2. Confirm main and a clean tree before syncing. Enter the full merge SHA from GitHub when prompted. These checks stop the handover if main has moved since approval.

~~~powershell
if ((git branch --show-current) -ne 'main' -or (git status --porcelain) -or $LASTEXITCODE) { throw 'Expected clean main' }
$approved = (Read-Host 'Approved full merge SHA').Trim()
git fetch origin main
if ($LASTEXITCODE -or $approved -notmatch '^[0-9a-f]{40}$' -or (git rev-parse refs/remotes/origin/main) -ne $approved) { throw 'Review remote main before proceeding' }
git merge --ff-only $approved
if ($LASTEXITCODE -or (git rev-parse HEAD) -ne $approved) { throw 'Unexpected deployed HEAD' }
git log -1 --format='%H %s'
~~~

3. Inspect the existing listener and any task of this name. Confirm its owner, command line and launch console before stopping the temporary server with **Ctrl+C in its own console**. If the process is unfamiliar, pause the handover. Verify port 8080 is free.

~~~powershell
Get-NetTCPConnection -State Listen -LocalPort 8080 | Select-Object LocalAddress,LocalPort,OwningProcess
Get-ScheduledTask -TaskPath '\' -TaskName $task -ErrorAction SilentlyContinue | Select-Object TaskName,State,Description
if ([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners().Port -contains 8080) { throw 'Port 8080 is occupied' }
~~~

4. Install or repair the task. The installer recognizes the legacy task only at its original action, project path and description. It refuses foreign name collisions and refuses to replace a running definition.

~~~powershell
& $ps51 -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\install_waitress_task.ps1 -Mode Install -TaskUser $taskUser
if ($LASTEXITCODE) { throw 'Installation failed' }
& $ps51 -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\install_waitress_task.ps1 -Mode Check -TaskUser $taskUser
if ($LASTEXITCODE) { throw 'Task configuration failed verification' }
~~~

5. Check the reported principal, action, boot delay, ten retries, enabled state and IgnoreNew. Start the task once. Allow time for guards and PostgreSQL startup. Inspect the log if there is no listener.

~~~powershell
Start-ScheduledTask -TaskPath '\' -TaskName $task
Get-ScheduledTask -TaskPath '\' -TaskName $task | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskPath '\' -TaskName $task | Select-Object LastRunTime,LastTaskResult
Get-Content .\logs\production-waitress.log -Tail 45
~~~

6. Verify exactly one loopback listener, local HTTP and the public endpoint. The read-only health script uses HEAD, checks the app hostname and forwarded HTTPS locally, and requires the exact 302 location /login/. The optional external request reports unreachable networks separately. Exit 1 indicates a local or Git failure. Exit 2 indicates an external-only failure. A Cloudflare Access challenge or other unexpected redirect needs separate inspection.

~~~powershell
& $ps51 -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\check_production_health.ps1 -Public
~~~

Expect WAITRESS_LISTENER=PASS, LOCAL_HTTP=PASS, GIT_STATE=PASS and PUBLIC_HTTP=PASS. From a second computer or phone, open https://app.delisky-dz.com/, sign in and open an existing database-backed page. Record the time and result. Sign out of the Windows admin session, leaving the server powered on. Refresh the page from the second device. Sign back into Windows, repeat step 1, then recheck task state and health.

7. **Controlled crash drill.** During the agreed interruption window, verify exactly one listener. Pin its process handle, confirm its command and verify the complete ancestry up to the project's attached task launcher. Run the kill line only after the guard succeeds in this same session. If the guard throws, omit the kill and inspect manually. Stop-ScheduledTask requests a deliberate stop and is unsuitable for this recovery test.

~~~powershell
$rows = @(Get-NetTCPConnection -State Listen -LocalPort 8080 -ErrorAction Stop)
if ($rows.Count -ne 1 -or $rows[0].LocalAddress -ne '127.0.0.1') { throw 'Listener mismatch' }
$target = Get-Process -Id $rows[0].OwningProcess -ErrorAction Stop
$null = $target.Handle
$server = Get-CimInstance Win32_Process -Filter "ProcessId=$($target.Id)"
$expectedPython = Join-Path $project '.venv\Scripts\python.exe'
$expectedLauncher = Join-Path $project 'scripts\start_production_waitress.ps1'
$taskRunning = (Get-ScheduledTask -TaskName $task -TaskPath '\').State -eq 'Running'
$node = $server
$venvSeen = $false
$launcherSeen = $false
for ($i=0; $node -and $i -lt 5; $i++) { if ($node.ExecutablePath -eq $expectedPython) { $venvSeen = $true }; if ($node.ExecutablePath -eq $ps51 -and $node.CommandLine -like "*-File `"$expectedLauncher`"*") { $launcherSeen = $true; break }; $node = Get-CimInstance Win32_Process -Filter "ProcessId=$($node.ParentProcessId)" }
$verified = $taskRunning -and $venvSeen -and $launcherSeen -and $server.Name -eq 'python.exe' -and $server.CommandLine -match '(?:^|\s)-m\s+waitress\s' -and $server.CommandLine.Contains('--listen=127.0.0.1:8080') -and $server.CommandLine.Contains('config.wsgi:application')
if ($verified -and -not $target.HasExited) { $target.Kill() } else { throw 'Process identity unconfirmed; stop the drill' }
~~~

Wait about 60–120 seconds. Repeat step 6, compare the new PID with $target.Id, and verify one listener plus a new startup timestamp. Confirm recovery from the second device.

8. **Controlled reboot.** With applications closed and operator approval for the maintenance window, restart Windows normally. From the second device, verify access **before** logging into Windows. After signing in, repeat step 1, the task inspection and public health check. Record boot time, last task run/result, listener PID and second-device result. The last result may indicate a running task (0x41301). A status code alone does not prove HTTP health.

## Logs, emergency launch and rollback

The launcher appends to logs\production-waitress.log and rotates the previous transcript to .log.1 at startup when the current log exceeds 10 MiB. Both are ignored by Git. Look for start and stop timestamps, guard results, exit code and fatal reason. If execution fails before the transcript opens, inspect Task Scheduler's result and its Operational history when available.

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
