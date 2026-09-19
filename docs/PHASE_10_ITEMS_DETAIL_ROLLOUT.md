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
does not replace it. On a fresh target database, run both dry-runs in this
order:

```powershell
python manage.py provision_phase10_reference_data --settings=config.settings.development
python manage.py provision_items_detail_reference_data --settings=config.settings.development
```

Both dry-runs must finish with `DRY RUN: PASS`.

Apply only to the intended database, in the same order:

```powershell
python manage.py provision_phase10_reference_data --apply --settings=config.settings.development
python manage.py provision_items_detail_reference_data --apply --settings=config.settings.development
```

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

Uploading the exact same source file again after it already has derived review
batches is rejected instead of creating duplicate analytical data.

## Review and approval

A transaction-detail batch can be approved only when:

- status is `REVIEWED`;
- blocking error count is zero;
- staged row counts still match the reviewed totals;
- transaction-level truck scope exists;
- the replacement-plan snapshot exists;
- the replacement plan recomputed at approval is exactly the same as the one
  reviewed earlier;
- every replacement target is still `APPROVED`.

Review and approval for a source system are serialized through a source-system
database lock. Approval then supersedes all covered replacement targets in the
same transaction.

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

Run all of the following on the release candidate:

```powershell
python manage.py check --settings=config.settings.development
python manage.py makemigrations --check --dry-run --settings=config.settings.development
python manage.py test --settings=config.settings.development
```

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
