# Ask DELISKY — DEV operational closure

Base: `690e508`, `feature/items-transaction-detail`. This follow-up resolves
cold-provider timeout and optional revision-trigger ownership. The established
performance design and analytical data are unchanged.

## Ask-only timeout

`config.settings.development` now defines
`ASK_DELISKY_REQUEST_TIMEOUT_SECONDS = 180`. This is the normal operational
default for Ask, not a measurement-command override. The previous measured
cold inference was 126.277 seconds, already above the legacy 120-second
timeout. 180 seconds provides approximately 54 seconds of headroom and was
previously sufficient on this host; it is not a general latency guarantee.

Ask provider precedence:

1. Environment `ASK_DELISKY_REQUEST_TIMEOUT_SECONDS`, when present.
2. Django setting of the same name for normal application calls.
3. Legacy `ASK_DELISKY_TIMEOUT_SECONDS` (existing default behavior).

An explicitly injected `environ` mapping is self-contained and does not
inherit the Django default. All resolved values retain positive-integer
validation. A copied mapping is passed to the shared config parser; the
process environment and shared `.env` are never rewritten.

Marketing Helper still uses its original provider factory and legacy
`ASK_DELISKY_TIMEOUT_SECONDS`. It ignores the Ask-only override. Production
settings have not been edited; a future authorized rollout can configure the
Ask-specific environment variable independently of Marketing.

## Optional triggers, deterministic schema

Fresh migrations create the idle `AskDeliskyDataRevision` table only. They do
not install trigger functions or triggers on source tables. Keeping the small
table in common schema preserves a uniform Django migration state. Without
explicit trigger provisioning it has no revision writes or source-write locks;
the disabled cache also performs no revision reads.

The pre-release `0004` has been reduced to schema creation. New migration
`0005` removes old implicit triggers/functions from databases that previously
applied the original `0004`; cleanup is idempotent on fresh installations.
Reversing `0005` also removes optional tracking before a later reversal of
`0004` could drop its table. It never implicitly reinstalls triggers.
There is no migration branch on database name or deployment settings.

Revision triggers are owned by an explicit operational command:

```powershell
$env:DB_NAME = "delisky_bi_dev"
.\.venv\Scripts\python.exe manage.py migrate --settings=config.settings.development
.\.venv\Scripts\python.exe manage.py configure_ask_context_cache --enable --settings=config.settings.development
.\.venv\Scripts\python.exe manage.py configure_ask_context_cache --status --settings=config.settings.development
```

The command requires `ASK_DELISKY_CONTEXT_CACHE_ENABLED` to enable tracking.
It is not called at startup or by migrations. `--disable` removes tracking;
`--status` reports whether all six source triggers are present and enabled.
Turning the application cache flag off does not itself execute database DDL;
use `--disable` to remove previously opted-in tracking and its write overhead.
Enable/disable operations are transactional, lock source writes during the
transition, and rotate the revision token so previously cached context cannot
survive an interval of untracked changes.

Every cache revision read verifies all required triggers. If even one is
missing/disabled, the request builds fresh analytics and neither consumes nor
publishes shared cache entries. Ordinary uncached operation remains available.

DEV was migrated through `0005` and explicitly enabled afterward. No migration,
command, setting change, deployment or service action was applied to Production
or Waitress. Production migrations therefore do not impose revision-write
overhead merely because this DEV feature exists.

## Verification

Final targeted tests: **153/153 passed**. Full suite: **1197/1197 passed**.
Django system checks, migration drift (`makemigrations --check --dry-run`),
pending migration check (`migrate --check`), and `git diff --check` passed.
The final DEV tracking status is `enabled`.

Real smoke used account `rachidone1`, `delisky_bi_dev`, development settings,
2026-04-04 through 2026-08-26, all brands, and `qwen3:4b-instruct`.
No timeout environment variable was set or changed by the smoke script/command.
It confirmed Ask timeout 180, Marketing timeout 120, and no Ask-specific
environment override. The named Qwen model was unloaded before the first
request (without restarting Ollama or any application service).

| Stage | Cold | Warm |
|---|---:|---:|
| Analytics build | 116.004 s | not called |
| Qwen/Ollama | 122.478 s | 24.292 s |
| Total request | **238.652 s** | **24.310 s** |
| Input tokens reused / total | 0 / 3075 | 3074 / 3075 |
| HTTP | 200 | 200 |
| Completion | stop | stop |

Both responses used schema `2`, contained supported figures and analytical
limitations, and used identical serialized context. Warm cache lookup,
including tracking verification, took 2.193 ms. Qwen was called separately
for both questions; no answer cache is involved.

The remaining limitation is cold latency (~4 minutes end to end on this host).
The 180-second provider timeout covers inference, not analytics plus inference.
These successful measurements do not guarantee completion under arbitrary load;
cache remains per process and existing scope/invalidation limits still apply.
