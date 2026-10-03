"""Bounded DEV cache of immutable, provider-safe deterministic context.

The database revision changes transactionally via statement triggers, including
bulk/SQL writes. Questions, answers, users and ORM objects are never cached.
"""

from collections import OrderedDict
from threading import RLock
from time import monotonic

from django.conf import settings
from django.db import connection

from .models import AskDeliskyDataRevision


CACHE_TTL_SECONDS = 300
CACHE_MAX_ENTRIES = 8
CACHE_VERSION = "ask-context-v2-1"
_entries = OrderedDict()
_entries_lock = RLock()
# Fixed-size locks prevent duplicate builds without an unbounded lock registry.
_build_locks = tuple(RLock() for _ in range(16))


def clear_context_cache():
    with _entries_lock:
        _entries.clear()


def _data_revision():
    revision, _ = AskDeliskyDataRevision.objects.get_or_create(pk=1)
    return revision.token


def get_manager_context(*, period_start, period_end, brand_id, build):
    """Reuse context only for identical scope and committed data revision.

    Bypass transactions so uncommitted data can neither consume nor populate
    shared entries. A write during a build prevents that result being cached.
    Authorization remains in the view and provider availability is resolved
    before this function. Current manager context has no per-user data scope.
    """
    if not getattr(settings, "ASK_DELISKY_CONTEXT_CACHE_ENABLED", False):
        return build()
    if (
        connection.vendor != "postgresql"
        or connection.settings_dict["NAME"] not in {
            "delisky_bi_dev", "test_delisky_bi_dev"
        }
        or connection.in_atomic_block
        or not connection.get_autocommit()
    ):
        return build()

    scope = (
        CACHE_VERSION,
        connection.alias,
        connection.settings_dict["HOST"],
        connection.settings_dict["PORT"],
        connection.settings_dict["NAME"],
        period_start,
        period_end,
        # Preserve distinctions such as bool vs int in direct runtime calls.
        type(brand_id),
        brand_id,
    )
    with _build_locks[hash(scope) % len(_build_locks)]:
        revision = _data_revision()
        key = (scope, revision)
        now = monotonic()
        with _entries_lock:
            expired = [k for k, (until, _) in _entries.items() if until <= now]
            for expired_key in expired:
                del _entries[expired_key]
            cached = _entries.get(key)
            if cached is not None:
                _entries.move_to_end(key)
                return cached[1]

        context = build()
        if _data_revision() == revision:
            with _entries_lock:
                _entries[key] = (monotonic() + CACHE_TTL_SECONDS, context)
                _entries.move_to_end(key)
                while len(_entries) > CACHE_MAX_ENTRIES:
                    _entries.popitem(last=False)
        return context
