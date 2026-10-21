# Production autostart recovery

Incident reported on 2026-10-21: boot at 09:45:21, Cloudflared returned,
Waitress did not, no expected task was found, and no listener existed on 8080.
These incident facts were supplied by the operator. The launcher lacked an explicit
working directory; launching outside the project caused `No module named config`.
Likely outage mechanism: boot without a working Waitress autostart mechanism.
Why the task was absent is unknown. No evidence attributes deletion to Windows Update.
This repair session could not read Windows event logs or Task Scheduler through CIM.

Boot -> SYSTEM Scheduled Task -> production launcher -> Waitress 127.0.0.1:8080
-> Cloudflared -> Cloudflare. Leave the healthy Cloudflared service unchanged.

The existing `scripts/install_waitress_task.ps1` manages one root-folder task:
`DELISKY Production Waitress`. SYSTEM, service account, limited run level,
startup plus 30 seconds, IgnoreNew, start when available, no execution timeout,
no battery stop, three retries at one-minute intervals. Reinstallation uses -Force;
it does not add another task. Do not reinstall/start while an unmanaged healthy
Waitress owns 8080 without planning a controlled handover.

After CI passes and the PR is merged, sync clean main with origin/main. In an
Administrator PowerShell, from the project:

```powershell
.\scripts\install_waitress_task.ps1 -Mode Install
.\scripts\install_waitress_task.ps1 -Mode Check
```

Before starting as SYSTEM verify that SYSTEM can read the project, .venv, .env,
staticfiles and write logs, and that PostgreSQL authentication works for that
context. Credentials remain outside the repository and task arguments. The
launcher forces DB_NAME=delisky_bi and production settings; production settings
also reject other databases. It never runs migrations.

Logs: `logs\production-waitress.log`, previous rotation `.log.1` at 10 MiB.
Transcripts include timestamp, guards, branch/SHA, checks, listener and exit code.
Logs may contain framework diagnostics; restrict access to operators and SYSTEM.
A clean Waitress exit (0) is not a failure and does not trigger failure retries.
After three failures inspect the log and fix the failing guard before starting again.

Safe manual recovery, only after confirming 8080 is unused:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Delisky Self-host\DELISKY_BI\scripts\start_production_waitress.ps1"
```

For managed startup use `Start-ScheduledTask -TaskName 'DELISKY Production Waitress'`.
Verify Running, SYSTEM principal, task LastTaskResult and startup log; confirm the
listener PID belongs to the expected .venv Python/Waitress. Origin smoke:

```powershell
curl.exe -I -H "Host: app.delisky-dz.com" -H "X-Forwarded-Proto: https" http://127.0.0.1:8080/
Get-Service Cloudflared
```

Expected origin/app `/` -> 302 `/login/`; www `/` -> normal website redirect/page.
Check both public hostnames independently; matching responses alone do not prove
that both tunnel ingress rules target the same origin.

Simulate startup without reboot by starting the installed task when 8080 is free.
Only perform a controlled stop/start when a handover is required. Do not infer
reboot resilience from configuration alone: prove SYSTEM startup, listener and
public health. Never reboot automatically for this procedure.

Regression: `python scripts/tests/test_production_startup.py` uses isolated mock
executables; it never accesses Django, Production DB or actual scheduled tasks.
Windows CI parses scripts and runs those regressions. Production checks are
`manage.py check --settings=config.settings.production`, `manage.py migrate --check
--settings=config.settings.production` and `scripts/verify_static_manifest.py`,
with DB_NAME=delisky_bi. Do not run database-creating tests on Production.
