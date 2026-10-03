# Ask DELISKY performance hardening — DEV, 2026-10-03

## Scope and measurement

Base commit: `cd38e30`, branch `feature/items-transaction-detail`.
Real database: `delisky_bi_dev`; settings: `config.settings.development`;
user: `rachidone1`; period: `2026-04-04`–`2026-08-26`; all brands;
model: `qwen3:4b-instruct`.

Measurements use the Django HTTP request path with real analytics and Ollama,
with pass-through timing wrappers. No data or generated answer is mocked.
Both before/after measurement processes use the same temporary 180-second
provider timeout to observe completion; this is not the performance fix and
is not persisted to a shared environment file or service.

## Before

| Stage (seconds) | Initial request | Same question again |
|---|---:|---:|
| build_manager_insights | 119.779128 | 119.900591 |
| Context build, payload and JSON | 0.000384 | 0.000374 |
| Qwen/Ollama | 122.731566 | 21.425179 |
| Total HTTP request | 242.698845 | 141.340657 |

Ollama reported 3075 input tokens. Initial prompt evaluation took 94.517 s,
generation 21.216 s, and model loading 6.882 s. For the repeated question,
3074 input tokens were reused and prompt evaluation took 0.268 s.
Analytics were nevertheless rebuilt in full for each request.

## Change

- Cache only the immutable, sanitized `AskDeliskyContext`, in process memory.
  No ORM rows, user credentials, questions, or LLM answers are stored in it.
- Scope key: database identity, start/end dates, brand, schema/cache version,
  and committed source-data revision. Every question still invokes the provider.
- Maximum eight entries, five-minute TTL, LRU eviction, and a fixed set of
  build locks to suppress duplicate builds within one process.
- DEV-only enablement, with an additional allowlist for DEV/test database names.
  Disabled by default elsewhere; transactional callers bypass the cache.
- A transactional UUID revision is updated by PostgreSQL statement triggers
  on `ImportBatch`, `ImportRow`, `DistributionBrand`, `Truck`,
  `TruckCrewAssignment`, and `Worker`: the relations read by this analytics path.
  Bulk writes, direct SQL, deletion and truncation are included. Authentication,
  audit, rate-limit and unrelated source-configuration tables are excluded.
- Revision is global across these sources, intentionally conservative across
  brands and periods. It includes opening-stock changes before the selected
  period; it is not restricted to overlapping batches. Draft-source edits can
  cause an extra miss, but cannot cause stale reuse.
- Read the revision before/after a build; never publish a cache entry if data
  changed during that build. Rolled-back edits do not invalidate committed data.
- Place the complete unchanged context before the question in the provider
  prompt, allowing prefix reuse between different questions. No evidence,
  limitation, summary field, or token budget is removed or changed.

## Validation

- Targeted tests: 121 passed.
- Full suite: 1187 passed.
- Migration drift check and Django system checks: passed.
- Regression coverage includes scope/version/revision misses, different
  questions reusing analytics but receiving distinct provider answers,
  opening stock before the period, bulk edits, rollback, another connection's
  commit, changes during a build, bounded eviction/expiry, and concurrent builds.

## Operational limits

The cache is per process: another process or restart incurs a cold build.
Source changes invalidate all scopes rather than attempting fine-grained
dependency tracking. Revision updates serialize concurrent source writes on
one small row until transaction commit; context reads use normal MVCC reads.
If the analytics path gains a new database source, extend the trigger list and
regression coverage before enabling caching for it. Database restore should be
paired with application restart; manually disabling database triggers is unsupported.

Only the DEV migration was applied. No Production, Waitress, scheduled task,
deployment, or `main` operation was performed.

## After

| Stage (seconds) | Cold request | Same question, both caches warm | Different question, same scope |
|---|---:|---:|---:|
| build_manager_insights | 115.186443 | 0 (not called) | 0 (not called) |
| Context construction | 0.000326 | 0 (not called) | 0 (not called) |
| Cache/revision overhead | 0.004046 | 0.000959 | 0.000708 |
| Payload + JSON | 0.000171 | 0.000232 | 0.000204 |
| Qwen/Ollama | 126.276796 | 27.727977 | 20.087275 |
| Total HTTP request | **241.622679** | **27.744670** | **20.100044** |

Repeated total fell from 141.341 s to 27.745 s: **80.37% reduction**,
despite variation in the number of output tokens. Cold total is essentially
unchanged (242.699 s before vs 241.623 s after); this is not a cold-build
optimization. The before repeated run isolates warm Qwen with uncached
analytics; the after repeated run adds the warm analytics cache.

Ollama reported:

| State | Input tokens reused / total | Prompt evaluation | Output tokens | Generation |
|---|---:|---:|---:|---:|
| Cold | 0 / 3075 | 92.536 s | 129 | 28.544 s |
| Same question | 3074 / 3075 | 0.229 s | 126 | 27.384 s |
| Different question | 3039 / 3072 | 3.717 s | 75 | 16.268 s |

All three requests returned HTTP 200, schema `2`, supported analytical
figures and limitations, and `done_reason=stop`. Each made a real provider
call. The exact serialized context was 7736 UTF-8 bytes with identical
SHA-256 `664e6f4cf349290b9030cb3dbbd781764ebfb9728f0844cfa71d160d69c2d753`
across all three requests; questions differed in the third request.

The cold provider call still took 126.277 s, so a 120-second provider timeout
remains insufficient for this measured cold run. The temporary 180-second
measurement timeout is still needed for cold inference on this host, while
both warm requests completed in under 28 seconds. No persistent timeout
change was made. These are individual host measurements, not percentile or
multi-process load benchmarks.
