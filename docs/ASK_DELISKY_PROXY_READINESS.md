# Ask DELISKY proxy-safe transport (DEV rollout)

## Decision

Use POST + Server-Sent Events on the existing authenticated Ask endpoint.
DEV enables `ASK_DELISKY_STREAMING_ENABLED`; other settings retain the existing
JSON response until a separately approved rollout. No production deployment,
Waitress configuration, database, analytics calculation or context cache change
is part of this work. Marketing Helper continues to return JSON.

The validated cold baseline was 238.652 s (116.004 s analytics, 122.478 s Qwen).
Both stages run in a bounded background thread while the WSGI response emits
an immediate `accepted` event, then a `progress` event every 10 s, and finally
`result` or `error`. Progress means the operation is still running, not a
percentage or an assertion that the model has started generating tokens.

Cloudflare documents Proxy Read Timeout as the maximum interval between reads
from origin, with a default of 125 s. The transport keeps that interval short
during **both analytics and inference**, without changing any timeout.
`text/event-stream`, `Cache-Control: no-store, no-cache, no-transform`, and
`X-Accel-Buffering: no` prevent normal caching/transformation/buffering. An
upstream that explicitly buffers streaming responses must be configured to
pass them through before a future deployment.

References:
- https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/
- https://developers.cloudflare.com/api/resources/zones/
- https://docs.djangoproject.com/en/5.2/ref/request-response/#streaminghttpresponse-objects
- https://docs.pylonsproject.org/projects/waitress/en/latest/arguments.html

Polling was rejected for this scope: reliable result retrieval requires a job
lifecycle and retained answers. SSE needs neither Redis/Celery nor a result
store. Ollama still uses `keep_alive=5m`; unloading/restarting/evicting the model
remains safe because heartbeats do not depend on model warmth. Ask's configured
provider timeout remains 180 s. Context content, evidence and limits are intact.

## Resource and security contract

- Authentication, Manager-only authorization, CSRF, form checks and database
  rate limiting happen before starting the stream. Invalid requests keep their
  ordinary short JSON error/status. Forbidden roles cannot start work.
- One computation per application process; no waiting job queue. Busy requests
  receive 503 with `Retry-After: 10` and the existing unavailable audit outcome.
  WSGI streaming occupies one request thread; provision at least two request
  threads per process. The DEV smoke uses four, without touching a running
  service. The semaphore is per process, not a distributed capacity limit.
- The worker owns its database connections and closes them when finished.
  The capacity slot is released only after computation and database cleanup.
- Answers exist only in request/transport memory until sent or discarded.
  They are never saved in a database/cache/file or available for replay.
  Every accepted question calls the provider again.
- The browser disables duplicate submit and never automatically reconnects or
  resubmits POST. Refresh/disconnect discards an undelivered answer; already
  running blocking work may finish and retains its capacity slot until then.
  A process restart loses an in-flight operation; the user can retry manually.
- Execution success/failure audits are retained without question/answer text.
  After SSE headers (HTTP 200), terminal failures carry `ok:false` and a logical
  `status` (e.g. 503); audit `http_status` retains that operation status.
  Audits describe execution, not proof of browser delivery, including when a
  browser disconnects. Audit-write failures never yield a successful answer.
- The stream has a 600 s lifetime ceiling, independent of the unchanged
  provider timeout. Expiry emits an error and discards subsequent output;
  Python cannot forcibly cancel a blocking DB/provider call. Capacity remains
  reserved until it exits. This bounds simultaneous work even after disconnect.

## Verification

Targeted Django tests: **141 passed**. Full Django suite: **1207 passed** in
147.682 s. Frontend parser tests: **5 passed** (split UTF-8/frame boundaries,
multiple events, terminal provider failure, truncated/malformed stream and
Marketing/validation JSON compatibility). Django check, migration drift and
pending-migration checks passed; there are no new migrations.

Coverage includes anonymous/Accountant/Super Admin/superuser/mixed-role denial,
CSRF, invalid form, rate limit, provider failure, success/failure audits,
repeated provider invocation, bounded capacity, disconnect cleanup and stream
deadline behavior. Existing deterministic-context cache regressions also pass.

The smoke uses a loopback-only isolated WSGI server plus a forwarding HTTP
proxy with a **125 s socket read timeout**, actual DEV data and local Qwen.
It does not mock analytics/provider, override the provider timeout, store model
answers, expose a public origin, or access a deployed Cloudflare route.
The latter requires a separate deployment verification; this is DEV readiness.

Measured on 2026-10-03, `config.settings.development`, `delisky_bi_dev`, user
`rachidone1`, all brands, 2026-04-04 through 2026-08-26, `qwen3:4b-instruct`.
The model was explicitly unloaded and context cache cleared before cold smoke.

| Measurement | Cold | Warm |
|---|---:|---:|
| First HTTP headers | 0.081 s | 0.091 s |
| First accepted event | 0.081 s | 0.091 s |
| Maximum interval without an event | **11.231 s** | **10.011 s** |
| Analytics | 115.734 s | not rebuilt |
| Context lookup including analytics | 115.785 s | 0.068 s |
| Qwen/Ollama | 129.945 s | 25.613 s |
| Final completion | **245.828 s** | **25.784 s** |
| SSE frames | 26 | 4 |
| Terminal result / audit | success / success | success / success |

Both requests invoked Qwen once. The cold stream stayed healthy beyond 125 s
without changing the proxy/provider timeout; its longest gap was 11.231 s.
Compute latency remains comparable to the old 238.652/24.310 s baseline;
the improvement is early response and continuous transport activity.

Reproduce from the repository using the DEV virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_ask_proxy.py
node --test apps/dashboard/tests_js/ask_streaming.test.cjs
```

The smoke asserts DEV settings/database and the real 180 s provider setting,
rejects an Ask-specific environment override, and writes timing/count metadata
only to the OS temporary directory (`delisky_proxy_smoke_results.json`). It
creates a temporary DEV login session and two normal audited/rate-limited Ask
requests. It does not restart or reconfigure any existing server. The cold
assertion intentionally requires a run longer than 125 s on this host.
