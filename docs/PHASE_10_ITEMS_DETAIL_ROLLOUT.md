# Phase 10 — Items Transaction Detail Rollout Runbook

## Purpose

This runbook covers the safe rollout of transaction-level Items imports for
BIFA, DELISKY and NITA. It is intentionally separate from the current
Production environment until the feature branch is reviewed and approved.

The detail pipeline keeps the raw export, maps each source user to a route,
stores the exact sale datetime per accepted row, derives one reviewed batch per
brand, and replaces the covered legacy per-truck Items batches only at approval
time.

## Safety rules

- Never run DEV commands against `delisky_bi`.
- Never hard-code DEV batch or database ids in Production procedures.
- Keep `main` and Production unchanged until the feature PR is explicitly
  approved for deployment.
- Take and verify a database backup before any Production provisioning or
  import.
- Run reference provisioning in dry-run mode first.
- Approval is the point that supersedes previous analytical Items batches;
  review alone must not change approved analytics.

## Reference data

The detail provisioning extends the existing Phase 10 reference baseline; it
does not replace it.

For **DEV**, explicitly point `DB_NAME` at `delisky_bi_dev` and run both
dry-runs in this order:

```powershell
$env:DB_NAME = "delisky_bi_dev"
python manage.py provision_phase10_reference_data --settings=config.settings.development
python manage.py provision_items_detail_reference_data --settings=config.settings.development
```

Both dry-runs must finish with `DRY RUN: PASS`.

Apply to DEV only after those checks:

```powershell
$env:DB_NAME = "delisky_bi_dev"
python manage.py provision_phase10_reference_data --apply --settings=config.settings.development
python manage.py provision_items_detail_reference_data --apply --settings=config.settings.development
```

For **Production**, do not reuse the DEV commands or `delisky_bi_dev`.
After backup verification and explicit deployment approval, use
`config.settings.production` with the Production environment variables and
first verify that the resolved database is `delisky_bi` before any
`--apply` command.

The base command provisions the confirmed Phase 10 product aliases, exclusions
and generic route workers. The detail command adds transaction-detail route
mappings/exclusions and the historical BIFA route identities required by the
new exports.

Both commands are designed to be idempotent. The detail command validates
mapping/exclusion and primary-seller assignment conflicts before writing.
Historical generic BIFA seller assignments are evidence-bounded to
the accepted transaction-detail activity:

| Worker | Route | Start | End |
| --- | --- | --- | --- |
| GEN-BIFA-LIV04 | BIFA LIV04 | 2026-04-04 | 2026-06-20 |
| GEN-BIFA-LIV05 | BIFA LIV05 | 2026-04-04 | 2026-04-15 |
| GEN-BIFA-PLIV07 | BIFA PLIV07 | 2026-05-13 | 2026-06-23 |
| GEN-BIFA-PSLIV01 | BIFA PSLIV01 | 2026-04-08 | 2026-04-08 |

These identities are analytical placeholders, not real employee identities.

## Accountant upload flow

Use the **Items DETAIL** panel for transaction-level exports:

- BIFA detail export -> source system `BIFA_MILA`.
- AIO detail export -> source system `AIO_WEB`; the system partitions it into
  DELISKY and NITA derived batches.
- The legacy per-truck Items panel remains available only for old-style files.

Each raw file is stored once as an immutable source upload. Derived brand
batches keep:

- covered truck scope;
- exact mapping/exclusion snapshot used at review time;
- reviewed replacement batch ids;
- content hash;
- source audit metadata, including excluded source-user counts.

Uploading the exact same raw source again is handled by batch state:

- if every existing derived batch is still mutable (`PENDING`, `REVIEWED`,
  `BLOCKED` or `FAILED`), the review is refreshed in place instead of
  creating duplicate batches;
- if any derived batch is already `APPROVED` or `SUPERSEDED`, the source is
  treated as immutable history and the re-review is rejected;
- if a refreshed source no longer produces a previously mutable brand
  partition, that stale mutable batch is removed in the same transaction.

## Review and approval

A transaction-detail batch can be approved only when:

- status is `REVIEWED`;
- blocking error count is zero;
- staged row counts still match the reviewed totals;
- transaction-level truck scope exists;
- the source mapping/exclusion scope fingerprint still matches the exact
  fingerprint captured at review time;
- the replacement-plan snapshot exists;
- the replacement plan recomputed at approval is exactly the same as the one
  reviewed earlier;
- every replacement target is still `APPROVED`.

Review/refresh and all source-backed Items approvals (legacy and DETAIL) are
serialized through the same source-system database lock. The lock order is
intentionally consistent:
source system -> source upload -> derived batch -> replacement batches. This
avoids legacy/detail races and refresh/approval deadlocks while keeping
approval atomic. If mapping or exclusion reference data changes after review,
DETAIL approval stops and requires a fresh review instead of approving rows
prepared under stale route scope. Approval then supersedes all covered
replacement targets in the same transaction.

The batch detail screen shows the covered trucks, source exclusions, immutable
source-file hash and the prior batches that are expected to be replaced.

## Confirmed DEV evidence

Real protected exports were validated in DEV for the period
2026-04-04 through 2026-08-26.

### BIFA

- Detail batch: 94.
- Accepted rows: 130,446.
- Excluded recognized negative rows: 2.
- Source-excluded ADV rows: 280.
- Full-period quantity: 5,092,600 total units.
- Final worker attribution issues: 0.
- Legacy Items batches 52-58 were superseded in DEV.

### DELISKY

- Detail batch: 95.
- Accepted rows: 23,020.
- Full-period quantity: 45,152 total units.
- July quantity: 5,745.
- Final attribution issues: 0.
- Legacy Items batches 59, 61 and 63 were superseded in DEV.

### NITA

- Detail batch: 96.
- Accepted rows: 31,998.
- Full-period quantity: 65,470 total units.
- July quantity: 10,857.
- Final attribution issues: 0.
- Legacy Items batches 60, 62 and 64 were superseded in DEV.

The AIO source excluded 1,182 non-route rows from distribution analytics:
RACHIDONE 590, RACHID 580 and ADV 12. Six NITA transactions with no client
remain valid for product/truck/seller/period analytics and are omitted from
client attribution.

DEV ids above are evidence only and must not be copied into Production logic.

## Required verification before Production

Run all of the following on the DEV release candidate:

```powershell
$env:DB_NAME = "delisky_bi_dev"
python manage.py check --settings=config.settings.development
python manage.py makemigrations --check --dry-run --settings=config.settings.development
python manage.py test --settings=config.settings.development
```

Before Production provisioning, separately confirm the Production settings
resolve the expected database name without changing data.

Also confirm:

- feature CI is green at the exact release commit;
- reference-data dry-run passes on the target database;
- backup restore verification is current;
- no unexpected mutable/approved Items overlap exists;
- the accountant Items DETAIL screen renders and review links open correctly;
- a controlled smoke import uses copied/test data before the first real
  Production approval.

## Production rollout order

1. Freeze imports briefly.
2. Create and verify the Production backup.
3. Deploy the reviewed code only after explicit approval.
4. Run Django checks and migration check.
5. Run base Phase 10 and Items-detail reference provisioning in dry-run mode.
6. Apply both provisioning commands, in order, only if both dry-runs are clean.
7. Upload BIFA and AIO detail sources through the accountant workflow.
8. Review derived batches and replacement plans before approval.
9. Approve one source/brand scope at a time.
10. Reconcile full-period and sample sub-period totals.
11. Confirm zero unexpected attribution issues.
12. Re-enable normal import operations and monitor the dashboard.

No Production action is authorized by this document itself.

## Production preflight evidence — 2026-09-21

The release-candidate DEV database was rechecked after bounding the four
historical generic BIFA seller assignments:

- BIFA detail batch 94 remained APPROVED.
- Source rows: 130,446.
- Included rows: 130,446.
- Full-period quantity: 5,092,600 total units.
- Attribution issues: 0.
- Historical generic assignment windows matched the observed accepted-row
  windows exactly.
- The local full project suite passed 1,142/1,142 tests at commit
  `7014b0b` before the production-safety follow-up changes.

Production backup/recovery was also exercised without changing Production
business data:

- the missing `DELISKY Daily Backup` scheduled task was recreated under
  `SYSTEM` for 23:00 daily;
- a scheduled smoke run completed with task result 0;
- the scheduled archive identified its source database as `delisky_bi`;
- `pg_restore --list` passed;
- the archive was restored into a temporary database successfully;
- the restore contained 31 public base tables, 48 Django migrations and the
  `btree_gist` / `plpgsql` extensions;
- the temporary restore database was deleted after verification.

A preflight incident exposed two safeguards that are now required:

1. An inherited shell `DB_NAME=delisky_bi_dev` can override values loaded
   from `.env`. Production settings therefore reject every database name
   except `delisky_bi`, and the backup helper receives an explicit expected
   database name and fails before `pg_dump` on any mismatch.
2. Production uses
   `CompressedManifestStaticFilesStorage`. New templates that reference new
   static assets require a fresh `collectstatic` before the new application
   process is started. A stale manifest produced a 500 for the manager page
   until `collectstatic` was run; the currently running Production process
   was intentionally not restarted as part of this feature preflight.

The repository now also contains `scripts/install_backup_task.ps1` so the
daily backup task can be checked/recreated reproducibly instead of relying on
manual Task Scheduler configuration.

### Reproducible backup task / restore commands

From an Administrator PowerShell on the Production host:

```powershell
.\scripts\install_backup_task.ps1 -Mode Check
```

If the task is missing or its action does not match the repository definition:

```powershell
.\scripts\install_backup_task.ps1 -Mode Install -StartNow
```

A manual Production backup must be explicit:

```powershell
Remove-Item Env:DB_NAME -ErrorAction SilentlyContinue

powershell.exe -ExecutionPolicy Bypass `
    -File ".\scripts\backup_delisky.ps1" `
    -DjangoSettings "config.settings.production"
```

The backup helper now requires the resolved database identity to match the
settings-specific expected name before `pg_dump` can run. Production backup
files remain prefixed `delisky_bi_`; development backup files are prefixed
`delisky_bi_dev_` to avoid confusing the two archives.

A restore test can be repeated without hand-written temporary scripts:

```powershell
Remove-Item Env:DB_NAME -ErrorAction SilentlyContinue

.\.venv\Scripts\python.exe .\scripts\verify_backup_restore.py `
    --backup "D:\DELISKY_BACKUPS\PostgreSQL\YYYY-MM-DD\delisky_bi_....dump" `
    --settings config.settings.production `
    --expected-source-database delisky_bi
```

The verifier checks the archive header database name, restores only into a
generated `delisky_bi_restore_verify_...` database, validates public tables /
Django migrations / extensions, and removes the temporary database in a
`finally` cleanup.

## Hardened Production rollout order

1. Confirm the exact approved release commit, branch and clean working tree.
2. Freeze imports briefly.
3. Run `scripts/install_backup_task.ps1 -Mode Check` from Administrator
   PowerShell and confirm the action matches the expected Production command.
4. Create a fresh Production backup and perform a restore verification.
5. Deploy the reviewed code only after explicit approval.
6. Ensure no inherited `DB_NAME` override is present, then run Production
   Django checks and the migration dry-run.
7. Run:
   `python manage.py collectstatic --noinput --settings=config.settings.production`.
8. Only after the correct release code and static manifest are in place,
   restart/start Waitress and smoke-test `/login/` and `/manager/`.
9. Run base Phase 10 and Items-detail reference provisioning in dry-run mode.
10. Apply both provisioning commands, in order, only if both dry-runs are
    clean.
11. Upload BIFA and AIO detail sources through the accountant workflow.
12. Review derived batches and replacement plans before approval.
13. Approve one source/brand scope at a time.
14. Reconcile full-period and sample sub-period totals.
15. Confirm zero unexpected attribution issues.
16. Re-enable normal import operations and monitor the dashboard.

No Production data provisioning, Items approval, merge to `main`, or
Production application restart is authorized by this document itself.
