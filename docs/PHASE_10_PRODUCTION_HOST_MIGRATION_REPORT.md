# DELISKY BI - Phase 10 Production Host Migration Report

Date: 2026-08-15
Phase: 10 - Real Data, Production Operation and Maintenance
Scope: Migration of DELISKY BI production runtime from the previous host to the new production computer, restoration of all production services, backup recovery, security hardening, AI runtime restoration, and full regression verification.

## Migration Status

Production host migration: PASS
Disaster recovery procedure: VERIFIED
Phase 10 overall status: IN PROGRESS

This report closes only the production-host migration and recovery work.
Real company data import, production data validation, analytics verification, monitoring, and operational maintenance remain Phase 10 work.

## New Production Host

Current project path:

C:\Users\Delisky Self-host\DELISKY_BI

Current hardware:

- CPU: Intel Core i7 8th Generation
- RAM: 16 GB
- System SSD: Samsung MZVLB256HAHQ-000L7, approximately 256 GB
- Dedicated backup HDD: WDC WD5000LPCX-24VHAT0, approximately 500 GB
- Backup disk serial: WD-WXH1EA64AK1P
- Backup drive: D:
- Backup root: D:\DELISKY_BACKUPS

The dedicated HDD was transferred from the previous production computer and retained its existing backup history.

## Runtime Versions

Verified on the new production host:

- Python: 3.14.6
- pip: 26.1.2
- Django: 5.2.16
- PostgreSQL: 18.6
- Git: 2.55.0.windows.4
- Waitress: 3.0.2
- Ollama: 0.32.13
- cloudflared: 2026.8.2
- age: 1.3.1

A new Python virtual environment was created on the new machine instead of reusing the copied virtual environment from the old host.

## Git Recovery and Repository State

Project repository recovery was verified before production activation.

Initial recovered baseline:

- Branch: main
- Phase 09 commit: cfad088
- Tag: phase-09-complete
- Working tree: clean

During the migration, the backup runtime was adapted to the new production host.

Migration commit:

8bf8dfe - fix: adapt backup runtime to new production host

Final repository state:

- HEAD/main: 8bf8dfe
- origin/main: 8bf8dfe
- medianet-backup/main: 8bf8dfe
- Working tree: clean
- git diff --check: clean

## GitHub Repository Reorganization

The production project is now maintained entirely under the DELISKY company GitHub account.

Primary repository:

Delisky-Dz/DELISKY_BI

Secondary backup repository:

Delisky-Dz/DELISKY_BI_BACKUP

Git remotes:

- origin -> Delisky-Dz/DELISKY_BI
- medianet-backup -> Delisky-Dz/DELISKY_BI_BACKUP

The previous personal-account backup repository is no longer required for the new production configuration.

The secondary company repository received:

- main branch
- full Git history
- phase-02-complete
- phase-03-complete
- phase-04-complete
- phase-05-complete
- phase-06-complete
- phase-07-complete
- phase-08-complete
- phase-09-complete
- stage-02-complete

## PostgreSQL Recovery

The latest verified PostgreSQL backup used during the migration was:

D:\DELISKY_BACKUPS\PostgreSQL\2026-08-12\delisky_bi_2026-08-12_230002.dump

Pre-restore verification:

- Dump size: 127,362 bytes
- SHA-256 matched the stored checksum
- pg_restore --list: PASS

Production database:

- Database: delisky_bi
- Application role: delisky_app
- Host: 127.0.0.1
- Port: 5432

Restore result:

- pg_restore exit code: 0
- Public tables: 25
- django_migrations rows: 41
- Extensions:
  - btree_gist
  - plpgsql

Django production connection after recovery: PASS

## PostgreSQL Security Hardening

The fresh PostgreSQL installation initially had:

listen_addresses = '*'

Network listeners were:

- 0.0.0.0:5432
- :::5432

This was corrected to:

listen_addresses = 'localhost'

Final listeners:

- 127.0.0.1:5432
- ::1:5432

Final pg_hba.conf active rules use scram-sha-256 and are limited to local connections:

- local all all
- host all all 127.0.0.1/32
- host all all ::1/128
- local replication all
- host replication all 127.0.0.1/32
- host replication all ::1/128

No PostgreSQL/5432 Windows Firewall rule was found opening the database externally.

Final Django database connection after PostgreSQL hardening: PASS

The PostgreSQL administrative password was recovered/reset locally during migration.
A temporary local authentication exception used during recovery was removed immediately afterwards.
Final pg_hba.conf verification confirmed that no trust authentication rule remained.

## Python Environment Recovery

The copied virtual environment from the old computer was not reused as the active runtime environment.

A new environment was created at:

C:\Users\Delisky Self-host\DELISKY_BI\.venv

requirements.txt installation: PASS

pip check:

No broken requirements found.

Django version:

5.2.16

## Waitress Production Runtime

Waitress production endpoint:

127.0.0.1:8080

Manual runtime verification:

- Port 8080 listening on 127.0.0.1
- app.delisky-dz.com host test: HTTP 200
- www.delisky-dz.com host test: HTTP 200
- Server header: waitress
- X-Forwarded-Proto handling: PASS
- Secure cookie behavior: PASS

The existing installation script was reviewed before use.

scripts/install_waitress_task.ps1 dynamically derives the project root and did not require a hardcoded old-host path update.

Windows Scheduled Task:

DELISKY Production Waitress

Final status:

- Task found: True
- Task state: Running
- Startup execution: verified
- Port after reboot: 127.0.0.1:8080

Waitress automatic production runtime: PASS

## Backup Runtime Migration

The previous backup runtime contained old-host-specific values:

- Project root: C:\Users\MediaNet\DELISKY_BI
- Backup root: H:\DELISKY_BACKUPS
- Backup disk letter checks: H:

The new host uses:

- Project root: C:\Users\Delisky Self-host\DELISKY_BI
- Backup root: D:\DELISKY_BACKUPS

scripts/backup_delisky.ps1 was updated so that:

- projectRoot is derived dynamically from PSScriptRoot
- backupRoot is D:\DELISKY_BACKUPS
- backupDrive is derived from backupRoot
- disk identity validation still uses the dedicated HDD serial
- capacity checks use the derived backup drive

Dedicated backup HDD verification:

- Disk: WDC WD5000LPCX-24VHAT0
- Serial: WD-WXH1EA64AK1P
- Serial match: True
- Disk health: Healthy
- Volume health: Healthy

## age Secret Encryption Recovery

The new computer did not initially contain age.exe.

age 1.3.1 was installed at:

C:\Program Files\age\age.exe

The existing recipient configuration remained valid:

config\backup_age_recipient.txt

Recipient validation:

- Present: True
- Format valid: True

The backup runtime was updated to use the fixed system-wide age executable first, while retaining fallback lookup behavior.

This allows the backup task to work under the Windows SYSTEM account.

## Manual Backup Verification

A complete manual backup was executed successfully on 2026-08-15.

Verified outputs included:

### PostgreSQL

- Custom-format database dump
- pg_restore archive verification
- SHA-256 checksum

### Project

- Git bundle
- git bundle verify: PASS
- Working-tree ZIP
- SHA-256 checksums

### Media

- Media ZIP
- SHA-256 checksum

### Secrets

- Encrypted .env age file
- SHA-256 checksum

### Retention

- Retention helper executed
- RETENTION_RESULT=PASS
- No emergency retention mode
- Existing historical backups preserved

Final manual backup message:

DELISKY backup completed successfully.

Independent SHA-256 verification was performed on five generated artifacts:

- PostgreSQL dump: PASS
- Git bundle: PASS
- Working-tree ZIP: PASS
- Media ZIP: PASS
- Encrypted .env: PASS

PostgreSQL dump independent pg_restore verification:

PG_ARCHIVE_VERIFY_EXIT=0

## Automated Backup Under SYSTEM

Windows Scheduled Task:

DELISKY Daily Backup

Schedule:

Daily at 23:00

Account:

SYSTEM

Initial SYSTEM execution exposed a Git security protection:

detected dubious ownership in repository

The production repository is owned by the Delisky Self-host Windows account while the backup task runs under SYSTEM.

A system-level Git safe.directory exception was added only for:

C:/Users/Delisky Self-host/DELISKY_BI

A dedicated temporary SYSTEM test confirmed:

- Git repository access: PASS
- git status --porcelain: clean
- LastTaskResult: 0

The temporary diagnostic task was removed after verification.

The real DELISKY Daily Backup task was then executed under SYSTEM.

Final automated backup result:

- LastTaskResult: 0
- PostgreSQL backup: PASS
- Git bundle: PASS
- Working-tree snapshot: PASS
- Git working tree clean
- Media backup: PASS
- Encrypted .env backup: PASS
- Retention: PASS
- Final message: DELISKY backup completed successfully.

Automated backup subsystem: PASS

## Cloudflare Tunnel Recovery

cloudflared was installed on the new host at:

C:\Cloudflared\bin\cloudflared.exe

Version:

2026.8.2

The existing production tunnel was reused.

Tunnel:

DELISKY-BI-PRODUCTION

A new connector was installed on the new production host instead of creating a new tunnel.

Windows service:

Cloudflared

Final service status:

- Running
- Automatic
- StartMode: Auto

Service command uses a protected token file under:

C:\ProgramData\cloudflared\token

The existing application routing and Cloudflare Access configuration were retained.

External verification from a mobile phone:

- www.delisky-dz.com: PASS
- app.delisky-dz.com: PASS
- Cloudflare Access: PASS

No direct PostgreSQL exposure or router port forwarding is used.

## Ollama and Local AI Recovery

Ollama was installed on the new computer.

Version:

0.32.13

Local API listener:

127.0.0.1:11434

No external Ollama listener was observed.

Production model restored:

qwen3:4b-instruct

Model size:

approximately 2.5 GB on disk

Direct Ollama generation test:

- Response: OLLAMA_OK
- done: True
- API generation: PASS

Runtime process verification showed the model active on CPU with context 4096.

## Ask DELISKY Verification

Ask DELISKY was tested through the real Manager interface.

First request after a cold model start took approximately 30 seconds.

A second request while the model remained loaded completed in approximately 4 seconds.

The assistant returned a valid application response.

Ask DELISKY runtime chain:

Manager UI
-> Django
-> Ask DELISKY runtime
-> Ollama
-> qwen3:4b-instruct
-> response

Result: PASS

The difference between the first and second request confirms the expected cold-start/model-load effect.

## Marketing Helper Verification

Marketing Helper was tested through the real application.

It returned a valid Arabic marketing response.

Observed generation time:

approximately 17 seconds

Result: PASS

## Restart / Recovery Test

A real Windows restart was performed after production services were restored.

No production service was manually started after reboot.

Post-restart verification:

### PostgreSQL

- Running
- Automatic
- localhost listener restored automatically

### Cloudflared

- Running
- Automatic

### Waitress

- DELISKY Production Waitress task: Running
- 127.0.0.1:8080: Listening

### Ollama

- Started automatically through the Windows Startup entry
- 127.0.0.1:11434: Listening

### Backup Scheduler

- DELISKY Daily Backup: Ready
- LastTaskResult: 0
- Next scheduled run retained

### External Access

After reboot, tested from mobile internet:

- www.delisky-dz.com: PASS
- app.delisky-dz.com: PASS

Production restart/recovery test: PASS

## Django and Migration Verification

After the production restart:

Django production system check:

System check identified no issues (0 silenced).

Migration check:

No changes detected.

Django version:

5.2.16

Git state:

- working tree clean
- git diff --check clean

## Test Database Recovery

The application role delisky_app intentionally does not have PostgreSQL CREATEDB permission.

Therefore the Django test database was created manually:

test_delisky_bi

Owner:

delisky_app

The test database also required the PostgreSQL extension used by the production schema:

btree_gist

Verified test extensions:

- btree_gist
- plpgsql

This allowed Django migrations containing GiST exclusion constraints to execute correctly in the test database.

No additional production database privilege was granted to delisky_app.

## Full Regression on New Production Host

Final full regression:

Found 691 test(s).

System check:

0 issues

Result:

Ran 691 tests in 64.595s

OK

Full regression result:

691/691 PASS

The test database was preserved for future regression runs.

## Final Production Verification

Final production check:

System check identified no issues (0 silenced).

Final Git state:

- Branch: main
- HEAD: 8bf8dfe
- origin/main: 8bf8dfe
- medianet-backup/main: 8bf8dfe
- Working tree: clean
- git diff --check: clean

## Migration Conclusions

The DELISKY BI production system was successfully recovered and migrated to the new production computer.

Verified components:

- Project repository and Git history
- PostgreSQL production database
- PostgreSQL local-only security
- Django runtime
- Waitress production server
- Automatic Waitress startup
- Cloudflare Tunnel
- Cloudflare Access
- Public website
- Private application
- Dedicated HDD backup system
- Daily automated backup under SYSTEM
- Backup retention
- SHA-256 integrity checks
- Git bundle backup
- Encrypted .env backup
- Ollama local AI runtime
- qwen3:4b-instruct
- Ask DELISKY
- Marketing Helper
- Automatic recovery after Windows restart
- Full Django regression suite

Production host migration status:

VERIFIED AND COMPLETE

## Remaining Phase 10 Work

The completion of the production-host migration does not close Phase 10.

The next Phase 10 operational work remains:

- Import real company Excel files
- Validate first production import batches
- Verify real OpeningStock behavior
- Verify daily/period Chargement imports
- Verify Items and sales-period accuracy
- Configure real workers and truck assignments
- Configure real truck crews where required
- Validate real STOPPED truck records
- Review production warnings and rejected rows
- Verify real manager dashboard indicators
- Verify Top 10 visit / no-visit results
- Verify worker and truck rankings using real data
- Validate Ask DELISKY answers against real imported data
- Monitor database growth and backup growth
- Verify scheduled backup results during normal daily operation
- Perform regular operational maintenance

## Conclusion

The new computer is now the verified DELISKY BI production host.

The migration and disaster-recovery procedure was tested using real restored backups, real production services, real external access, a real Windows restart, and the complete 691-test Django regression suite.

No open migration blocker remains.

Phase 10 continues with real production data import, validation, monitoring, and maintenance.
