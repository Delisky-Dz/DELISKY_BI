# Raw import filename compatibility audit

Date: 2026-10-13
Branch: `feature/import-filename-compat`
Base/HEAD: `c41ae023c817b77318aa09027a2164fd785f6663`
Initial working tree: clean (verified outside the restricted shell after its access error).

## Outcome

No production-code compatibility change was justified. Added seven behavioral tests in
`apps/imports/test_raw_filename_compatibility.py`. All 181 selected tests pass.
No models, schema, migrations, operational mappings, business rules, JavaScript or CSS changed.
No commit, push, merge, PR, deployment or production restart performed.

Opening Stock has an important content-dependent boundary: the supplied new name works
through the Raw accountant upload, review, preview and approval when the workbook has
canonical `VAN / Qte / Article` columns (the actual quantity header is `Qté`). The same
name does not identify a truck for the old designation/packaging export unless an explicit
mapping exists for that source. The actual newly exported workbook was not supplied, so
its structure and the meaning of `_01` remain unverified. This is not an unconditional
PASS for every possible workbook bearing that name.

## Audit matrix

| Report | Filename dependency and function | Existing name | New/dated name | Result / semantic boundary |
| --- | --- | --- | --- | --- |
| Sales | `raw_sales_file.source_truck_code_from_filename`; source token goes through data-driven mapping | `VAN1-NITA.xlsx`, `VAN1-NITA sales.xlsx` | `VAN1-NITA sales_2026-08-27_to_2026-10-08.xlsx` (also VAN1-3 for DELISKY/NITA) | Already supported. UI supplies review period; row date comes from workbook and is validated against it. Filename dates are not business metadata. |
| Chargement | `adapt_raw_chargement_file` / row adapter; filename is audit metadata | `chargement_raw.xlsx`, `Chargement_BIFA_2026-03-07_2026-03-11.xlsx` | `BIFA_Chargement_2026-08-27_to_2026-10-08.xlsx` | Already supported. Source comes from location fields in workbook, with existing mapping/exclusion and structural validation. |
| Items Detail | `adapt_raw_items_detail_file`; `Utilisateur` maps the source per row | `BIFA_Items_DETAIL_2026-04-04_to_2026-08-26.xlsx` | `BIFA_Items_DETAIL_2026-08-27_to_2026-10-08.xlsx` | Already supported through actual upload, review, preview and approval. UI supplies period; workbook supplies transaction dates; brand derives from resolved trucks. |
| Items | `raw_items_file.source_truck_code_from_filename`, then mapping | `DCV-03.xlsx`, `DCV-03 items.xlsx` | `DCV-03 items_2026-08-27_to_2026-10-08.xlsx` | Already supported. This dated example is representative; user supplied no specific new Items-only filename. Unlike Items Detail, legacy Raw Items does rely on filename source. |
| Opening Stock canonical | Helper is called, but `adapt_raw_opening_stock_row` uses canonical workbook VAN; brand partition resolves Truck.distribution_brand | `OpeningStock_NITA_2026-08-10.xlsx` | `OpeningStock_NITA_01_2026-08-10.xlsx` | Already supported through upload/approval. UI stock_date is authoritative. Tests also show a different filename brand/date does not override content/UI. |
| Opening Stock legacy raw | `raw_opening_stock_file.source_truck_code_from_filename` removes trailing opening/opning stock; remaining token maps to truck | `VAN1-NITA opning stock.xlsx` | `OpeningStock_NITA_01_2026-08-10.xlsx` | With only VAN1-NITA mapping, rejects via row_adaptation_failed / source_truck_not_mapped. No safe alias can be inferred from `_01`; no suffix stripping or mapping change applied. |

## Real call paths

- Sales: `RawSalesUploadForm` -> `raw_sales_upload` -> multi review -> derived review -> prepare review -> file adapter -> metadata cleaning/staging. Source system and review dates come from UI; source truck comes from filename and mapping.
- Chargement: `RawChargementUploadForm` -> `raw_chargement_upload` -> derived multi review -> derived review -> file/row adaptation -> brand partition -> metadata cleaning/staging.
- Items Detail: `RawItemsDetailUploadForm` -> `raw_items_detail_upload` -> multi review -> import review -> prepare review -> adaptation/brand partition/cleaning -> persistence. Preview reads the persisted batch. Approval dispatch identifies detail batches through coverage metadata and invokes detail approval; it does not parse the filename.
- Items: `RawItemsUploadForm` -> `raw_items_upload` -> multi review -> derived review -> prepare review -> file/row adapter. Source filenames also participate in existing overlap/replacement scope calculations through the same source helper.
- Opening Stock: `RawOpeningStockUploadForm` -> `raw_opening_stock_upload` -> multi review -> derived review -> file/row adaptation -> brand partition -> metadata cleaning/staging. UI chooses source system (BIFA/AIO) and stock_date. Canonical VAN resolves the truck and its stored distribution brand; old raw export needs the filename mapping.

Shared Excel readers validate extension, workbook readability and structure. Raw flows do
not call `run_import_preflight` or `parse_import_filename`. Original names are retained
in source-upload and batch audit records.

The separate standard upload uses `ImportUploadForm` and the generic parser; standard
batch review uses preflight. The generic parser intentionally returns brand `NITA_01`
for `OpeningStock_NITA_01_2026-08-10.xlsx`. Selecting NITA in the standard form therefore
produces a brand mismatch instead of silently changing the brand. The generic parser
and standard workflow have not been broadened to accept Raw export naming conventions.
The report-first legacy names in the request belong to this standard workflow and are
not interchangeable with source-first legacy Raw filenames.

## Changed files

- `apps/imports/test_raw_filename_compatibility.py`: seven tests, including Sales VAN1-3
  across both brands and old/new names, mapped Items sources, content-driven Chargement,
  Opening Stock legacy rejection safety, literal generic-parser brand suffix, and real
  accountant upload -> review -> preview -> approval for canonical Opening Stock and
  Items Detail. Workbooks are generated fixtures; mappings and product records exist
  only in the test database. Media files use temporary directories.
- `docs/import-filename-compat-audit.md`: this audit, boundaries, examples and results.

The first run had one test expectation typo (`unknown_source_truck_code` instead of the
existing `source_truck_not_mapped`). The assertion was corrected; no application code
was changed to make tests pass.

## Validation

Development settings were used explicitly with `DB_NAME=delisky_bi_dev`; Django tests
used the separate `test_delisky_bi_dev` PostgreSQL database with `--keepdb --noinput`.
The existing project virtual environment was reused. No production data was changed.

Raw selection: **138 passed, 0 failed**, including seven new tests with subcases.
All module names below have prefix `apps.imports.`:

- `test_raw_filename_compatibility`
- `test_raw_sales_file`, `test_raw_sales_views`, `test_raw_sales_derived_review`
- `test_raw_chargement_file`, `test_raw_chargement_forms`, `test_raw_chargement_views`, `test_raw_chargement_derived_review`
- `test_raw_items_detail_file`, `test_raw_items_detail_views`, `test_raw_items_detail_approval`, `test_raw_items_detail_multi_review`
- `test_raw_items_file`, `test_raw_items_views`, `test_raw_items_derived_review`
- `test_raw_opening_stock_canonical_snapshot`, `test_raw_opening_stock_file`, `test_raw_opening_stock_views`, `test_raw_opening_stock_derived_review`, `test_raw_opening_stock_brand_partition`

Standard selection: **43 passed, 0 failed**:

- `apps.imports.tests.ImportFilenameParserTests`
- `apps.imports.tests.ImportPreflightTests`
- `apps.imports.tests.ImportBatchReviewServiceTests`
- `apps.imports.test_accountant_views`

`manage.py check --settings=config.settings.development`: no issues.
`git diff --check`: clean; new files additionally checked with `git diff --no-index --check`.
Full suite and frontend tests were not run.

Final intended Git state: same branch/base, two new unstaged files listed above; no commit.
