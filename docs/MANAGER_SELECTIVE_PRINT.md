# Selective Manager Meeting Report

The shared Manager print action now opens `/print/` as a configuration page.
Only `/print/generate/` builds the selected meeting report. `/print/detail/`
retains its existing full-list behavior and authorization.

## Selection and execution

- Full (default): all ten allowed sections.
- Quick: overview, sellers, visits, actions.
- Manual: one or more allowlisted section IDs, repeated or comma-separated.
- Unknown presets/sections and empty manual selections return HTTP 400 before analytics.
- Auto-skip defaults on; `auto_skip=0` explicitly retains empty sections.
- Only rendered sections are numbered; the first selected section does not force a header-only page.
- Executive zero KPIs remain visible. KPIs whose modules were not loaded display unavailable.
- Existing client 10/category, product 15/category, seller-priority 5, and products/seller 5 limits remain.

Dependencies are deliberate and request-local:

| Selection | Required sources |
| --- | --- |
| Overview / sellers / visits | Shared sales and POS; existing seller presenters |
| Sales alone | Sales only; no POS or seller builders |
| Clients | Sales/POS and previous-period sales for existing classifications |
| Trucks | Existing operational-status service |
| Unsold / product alerts | Existing product-source aggregation; only chosen category presenters |
| Actions | Sales/POS, client priorities, product attention, truck status |
| Coverage | Existing data-quality builder and its source dependencies |

Sales, POS, indexes, product sources and operational status are reused when several
selected sections need them. Source metadata for the latest approved date uses one
aggregate query unless the coverage section itself is requested. No formulas,
classifications, imports, mappings, models or migrations were changed.

## Validation and timing (2026-11-08)

- Local full project suite: 1,302 tests passed before the final small presentation/test additions.
- Final focused print/configuration/action suite: 41 tests passed.
- Django system checks and Git whitespace checks passed.
- Regression tests fail immediately if overview+sellers invokes client, product,
  truck or coverage analytics. Product-only and sales-only execution are also checked.
- Detailed-report permissions, unbounded lists and meeting limits remain covered.

Reproduce the informational synthetic benchmark using:

```powershell
python manage.py test apps.dashboard.test_manager_selective_print.SelectivePrintTests.test_development_generation_timings --settings=config.settings.development --noinput
```

The benchmark creates 1,000 synthetic approved rows (200 each of SALES, POS,
ITEMS, OPENING_STOCK and CHARGEMENT), five trucks/sellers, and 40 clients, solely
in Django's disposable PostgreSQL test database. It measures end-to-end Django
client generation including HTML rendering, alternates preset order, discards
one warmup per preset and reports the median of seven samples. It has no
speed assertion and is not a Production benchmark.

| Preset | Final local median |
| --- | ---: |
| Quick | 0.217054 s |
| Full | 0.239413 s |

Quick was approximately 9.3% faster for this fixture. A separate read-only
measurement of the development database (all brands, 2026-08-27 through
2026-10-22, context + HTML rendering, seven warm samples) found no included
sales/POS records: Quick 3.290302 s / 13 queries, Full 3.225515 s / 25 queries.
That sparse-scope measurement ran alongside the full test suite and does not
establish a speed improvement. No Production timing claim is made.

No local Production deployment, collectstatic or migration was performed.

MANUAL ACCEPTANCE PENDING: Production configuration UI and PDF review.
