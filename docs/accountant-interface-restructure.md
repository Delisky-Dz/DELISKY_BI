# Accountant interface restructure

## Architecture

Before: `accountant_home.html` contained the canonical upload form, all five raw
upload panels, recruitment overview, import counters, and the latest 20 batches.
Every upload rendered that same page through `_home_context`, which instantiated
all forms and loaded unrelated counters and history. The sidebar history link
was an anchor on the landing page.

After: the landing page provides shortcuts and only the existing recruitment
badge count. It constructs no upload forms and queries no import history.
Each raw upload endpoint accepts GET to render its own form and retains its
existing POST processing. Both validation errors and multi-file review results
render the same dedicated section. `_upload_context` receives only that section's
form and result. A shared upload page includes the extracted, type-specific
partial; existing field names, formset prefixes, DOM identifiers, result markup,
and JavaScript hooks remain intact.

The batch list has its own page, status counters, and 20-row pagination so older
batches remain reachable. Detail pages return to that list. The sidebar groups
uploads, review/approval, and existing operational management pages. Active
states are rendered on the server; detail/approval belong to batch history.

## Routes

| URL | Behavior |
| --- | --- |
| `/accountant/` | Lightweight GET landing; original canonical POST remains supported |
| `/accountant/raw-opening-stock/` | Opening Stock GET and existing POST |
| `/accountant/raw-chargement/` | Chargement GET and existing POST |
| `/accountant/raw-items-detail/` | Items Detail GET and existing POST |
| `/accountant/raw-items/` | Items GET and existing POST |
| `/accountant/raw-sales/` | Sales GET and existing POST |
| `/accountant/batches/` | Batch history; optional `?page=2` |
| `/accountant/standard/` | Existing canonical upload form, now on its own GET/POST page |
| `/accountant/batches/<id>/` | Existing review/detail endpoint |
| `/accountant/batches/<id>/approve/` | Existing POST-only approval endpoint |

The extra `standard/` page preserves access to the pre-existing canonical import
workflow. Removing it would remove functionality and break the original upload
experience. Successful canonical uploads retain their existing detail redirect.

## Scope and compatibility

- No parsing, review, approval, filename rules, analytical rules, forms, models,
  migrations, or application settings changed.
- Existing Accountant/active-superuser access checks remain in place. Workforce
  and fleet retain their additional permission requirements, tested with the
  project's normal `seed_roles` fixture.
- Recruitment, workers, categories, capabilities, trucks, and crew view logic
  remain unchanged. Their links continue to use their existing routes.
- Arabic, RTL, theme storage key, Light/System/Dark controls, upload interactions,
  and shared design remain intact. Small landing-card CSS adjusts heading size.
- No production deployment, production database access, `.env` changes, or merge.

## Verification

Tests use a freshly initialized PostgreSQL 18 cluster on loopback port 55439,
inside the task workspace, with a test-only role. The development and test database
names are on that isolated server; credentials and configuration are supplied
directly to the test process without copying or reading any `.env`.

Targeted command:

```text
python manage.py test apps.imports apps.workforce apps.fleet apps.recruitment --settings=config.settings.development --noinput --keepdb
```

Full command:

```text
python manage.py test --settings=config.settings.development --noinput --keepdb
```

The new navigation tests cover authorized and unauthorized GET/POST requests,
section isolation on GET and invalid POST, landing-page query/form isolation,
canonical POST compatibility, pagination, and sidebar states including existing
management destinations. Existing successful/failed upload tests additionally
assert that only the relevant section is rendered. Existing approval tests remain
part of the targeted suite. A dedicated CI workflow reruns targeted, full, and
JavaScript checks for this branch and relevant pull requests to main.

Final local results, 2026-10-06:

| Check | Result |
| --- | --- |
| Targeted imports/workforce/fleet/recruitment | 728 passed, 113.953 seconds |
| Full Django suite | 1220 passed, 156.245 seconds |
| Django system check | No issues |
| JavaScript syntax, all application static JS | 5 files passed |
| Existing JavaScript regression tests | 5 passed |
| Accountant template compilation | Passed |
| Isolated collectstatic + hashed manifest resolution | All 20 template asset references passed |
| `git diff --check` | Passed |
| Structural comparison of POST processing | All six upload handlers unchanged apart from page rendering/GET routing |
| Structural comparison of batch detail/approval functions | Unchanged |

Initial test-fixture failures were corrected before the passing runs: required
batch uploader, canonical form's new location, and the seeded operational role
permissions. No failing tests remain in the final local runs.

The static build used a temporary output directory and development settings with
manifest storage overridden in the check process only. It did not load production
settings or change any settings file. Browser visual inspection was unavailable:
the browser automation kernel failed to initialize in this environment. RTL/theme
markup, form isolation, navigation, and template/assets were verified automatically;
visual acceptance at desktop/mobile sizes remains a pre-merge review item.

## Changed files

- `apps/imports/views.py`, `urls.py`: lightweight landing, dedicated GETs and
  rendering, canonical compatibility route, paginated history.
- `apps/imports/templates/imports/accountant_home.html`, `base.html`,
  `batch_detail.html`: landing, navigation inclusion, history return link.
- New `accountant_upload.html`, `accountant_batches.html` and nine partials:
  `opening_stock_upload.html`, `chargement_upload.html`, `items_detail_upload.html`,
  `items_upload.html`, `sales_upload.html`, `standard_upload.html`,
  `batch_list.html`, `batch_stats.html`, `import_navigation.html`.
- `apps/imports/static/imports/css/accountant.css`: landing shortcut headings/focus.
- `apps/imports/test_accountant_views.py`, five `test_raw_*_views.py` files,
  and new `test_accountant_navigation.py`.
- `.github/workflows/accountant-interface.yml`: isolated CI tests.
- This architecture/validation report.

Base: `main` at `677a9e6dcdee48e23cea3cb8b57e6f49d5ed0a80`.
Branch: `feature/accountant-interface-restructure`.

## Review decisions

No business-rule decision is needed. Review the dedicated canonical import entry,
paginated batch history, and visual appearance before any separately authorized
merge. The requested deliverable is a Draft PR only.
