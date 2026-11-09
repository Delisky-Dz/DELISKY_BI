# Lightweight meeting reports

Production acceptance reported roughly 65 seconds for Quick over 2026-08-01 through
2026-11-26. Earlier synthetic timings did not represent this experience.

## Dependencies

`plan_dependencies` is the server-side planner. Actions add no domain loads:

| Selected content | Required analytics |
| --- | --- |
| Overview / sellers / visits | Current sales and POS; existing seller presenters |
| Sales | Current sales |
| Clients | Current sales, POS, previous-period sales and existing classifications |
| Unsold / product alerts | Items, opening stock, chargement and product combination |
| Trucks | Operational status |
| Coverage | Existing complete data-quality/coverage audit, including its product and operational sources |
| Actions | Results already loaded by the selected content; decisions table always available |

Quick selects overview, sellers, visits and actions. It never loads client trends,
product sources, truck status or data quality. Optional executive KPIs retain their
neutral unavailable states. Seller unsold counts can use products loaded for another
selected module; detailed unsold seller cards require the explicit `unsold` selection.
Full still selects every domain. Detailed report construction and all underlying
business calculations and permission decorators are unchanged.

## Development benchmark

Run with the development environment configured:

```powershell
python manage.py benchmark_manager_print --settings=config.settings.development --period-start 2026-08-01 --period-end 2026-11-26 --samples 3
```

The command requires DEBUG, PostgreSQL and `delisky_bi_dev`, then enforces a read-only
transaction before validating filters or building contexts. It alternates preset
order, discards one warmup and prints stage medians and total context + HTML time.
It does not export data or add diagnostics to the public UI. Stages are inclusive:
coverage includes its nested product/operational sources; sales aggregation includes
previous-period sales when clients are selected. Client analytics reports presenter
and classification time separately. Totals include remaining presentation/orchestration.
Browser loading, PDF pagination and printing are outside this measurement.

The regression fixture benchmark is informational only (1,000 synthetic source rows,
five sellers/trucks). It cannot establish Production performance. Production timing
requires deployment and manual measurement using the same selected period and sections.

No database migrations or static asset changes are needed for this fix.
