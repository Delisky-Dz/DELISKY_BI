# Ask DELISKY — Production configuration readiness

This is a future operator runbook, **not authorization to deploy**. No Production
database, environment, service or trigger was changed during readiness work.
The DEV functional/performance/SSE closure remains the reference; do not repeat
those audits as part of configuration validation.

## Configuration contract

Production reads these opt-in flags after normal environment loading:

| Variable | Missing default | Accepted values |
|---|---|---|
| `ASK_DELISKY_STREAMING_ENABLED` | `False` | `true`, `false` |
| `ASK_DELISKY_CONTEXT_CACHE_ENABLED` | `False` | `true`, `false` |

Case and surrounding whitespace are normalized. Empty strings, `1`, `0`, `yes`
and all other values raise `ImproperlyConfigured` with the variable name.
Deployment does not activate either feature merely by importing the code.

`ASK_DELISKY_REQUEST_TIMEOUT_SECONDS=180` is the explicit Ask-only deployment
choice, using the existing provider factory validation/precedence. Without it,
the legacy shared timeout behavior is preserved. Do not change
`ASK_DELISKY_TIMEOUT_SECONDS` to tune Ask: Marketing still reads that shared
setting and is unaffected by the Ask-specific override. Provider mode/model/URL
remain explicit (`ASK_DELISKY_PROVIDER=local`, `ASK_DELISKY_LOCAL_MODEL=qwen3:4b-instruct`,
`ASK_DELISKY_LOCAL_BASE_URL=http://127.0.0.1:11434`). No provider request is made
by importing the settings or constructing the provider.

## Cache decision

Prepare **both SSE and deterministic analytics cache** for Production opt-in.
The former DEV database-name whitelist is replaced by the architectural gate:
explicit cache enablement, PostgreSQL, autocommit outside a transaction, and
verified revision triggers. Settings still reject the wrong database for each
environment. Database identity remains part of the cache key.

No calculations, evidence, limitations, revision scope, TTL/LRU limits or answer
caching behavior change. If required triggers are missing/disabled, cache reads
and writes are bypassed; analytics rebuild safely. Installation remains an
explicit operator command, never a migration/startup side effect. The six source
tables and transactional token rotation remain unchanged. Enabling tracking
introduces one revision write per source-changing statement and may serialize
concurrent source writers; provision in a maintenance window. Cache readiness
does not claim a new Production workload benchmark.

Waitress now passes a fixed **`--threads=4`**. One SSE request can occupy a
request thread while three remain available. The existing one-computation-per-
process limit remains; no unbounded executor/queue is introduced. Existing
branch, clean-tree, HEAD, static-manifest and Django launcher guards remain.

## Exact future rollout order

Perform only after merge/deployment approval, on the intended Production host.
Abort on a failed command; do not proceed to restart after a failed prerequisite.

1. Enter the maintenance window and prevent writes during deployment. Record
   the current release and configuration for rollback. Take the guarded backup:
   `scripts/backup_delisky.ps1 -DjangoSettings config.settings.production`.
   Confirm successful database/project/media backup and the established restore
   verification before continuing. Use the approved clean release checkout;
   launcher requires `main`, clean working tree and HEAD equal to `origin/main`.
2. With Production feature flags still false, apply schema migrations:
   `.venv/Scripts/python.exe manage.py migrate --settings=config.settings.production`.
   Then run `migrate --check` with the same settings. Migrations do not install
   revision triggers; do not edit migration files to activate tracking.
3. Build static assets:
   `.venv/Scripts/python.exe manage.py collectstatic --noinput --settings=config.settings.production`.
   Verify with `.venv/Scripts/python.exe scripts/verify_static_manifest.py` under
   `DJANGO_SETTINGS_MODULE=config.settings.production`. Confirm the manifest
   contains the updated dashboard JavaScript/SSE reader.
4. Set the approved Production service environment (not a temporary smoke-only
   override): `ASK_DELISKY_REQUEST_TIMEOUT_SECONDS=180`,
   `ASK_DELISKY_STREAMING_ENABLED=true`, `ASK_DELISKY_CONTEXT_CACHE_ENABLED=true`,
   and the explicit local provider/model/URL above. Ensure management commands
   and the service account see the same environment and the existing Production
   database/host/security configuration. Do not change Marketing's timeout.
5. Provision revision tracking explicitly under that environment:
   `.venv/Scripts/python.exe manage.py configure_ask_context_cache --enable --settings=config.settings.production`.
   Verify with the same command using `--status`; require output **enabled**.
   If cache is intentionally deferred, leave its flag false and skip enablement;
   that rollout has SSE protection but is not warm-analytics-cache acceptance.
6. Run `manage.py check --settings=config.settings.production`, then perform the
   approved service restart through `scripts/start_production_waitress.ps1`
   (or the existing scheduled task pointing to it). Require all launcher guards
   PASS and `WAITRESS_THREADS=4`. Do not bypass guards or start a second listener.
7. Through the real authenticated **Cloudflare-proxied browser route**, submit
   an approved cold analytical question. Verify immediate accepted event,
   approximately 10 s progress events during analytics AND inference, no long
   buffered gap/524, final answer, and success audit. A local smoke alone does
   not establish the behavior of the deployed proxy path. Coordinate any cold
   model unload in the maintenance window; keep_alive is not a correctness gate.
8. Submit another question in the same scope before cache expiry. Confirm warm
   analytics reuse and a separate provider invocation, successful completion
   and audit, correct evidence/limitations, and no retained answer/replay store.
   Only then declare Production rollout accepted and reopen normal operation.

Rollback: restore the prior approved release/configuration through the guarded
process. If disabling tracking, first turn cache off for serving processes and
restart safely, then run `configure_ask_context_cache --disable` and verify
`--status` reports disabled. Turning the flag off alone does not remove already
installed triggers. Never leave stale context reusable after untracked writes.

## Readiness validation

Configuration tests block database connections while importing Production
settings; they never connect to `delisky_bi`. Runtime/invalidation tests use DEV
test databases or fake connections. Existing SSE/cache regressions remain,
except the obsolete assertion that an explicitly opted-in Production database
must always bypass cache, which is replaced by explicit opt-in coverage.

GitHub Actions includes the full Django suite, existing PowerShell parser and
migration checks, plus SSE frontend tests. No workflow performs Production
migrations, enables triggers, restarts Waitress or calls the real provider.

Local readiness result (2026-10-03): **127 targeted / 1213 full Django tests /
5 frontend tests PASS**. All five PowerShell scripts parse successfully.
Django checks, migration drift/pending checks and diff checks pass. Isolated
Production static collection/manifest validation passes for all 20 template
references with database connections explicitly forbidden. No cold/warm model
smoke was repeated for this configuration-only change.
