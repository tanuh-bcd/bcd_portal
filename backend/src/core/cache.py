import os
import threading
import time

# Seconds a dashboard result is reused before it is recomputed. 0 disables caching.
DASHBOARD_CACHE_TTL_SECONDS = int(os.getenv("DASHBOARD_CACHE_TTL_SECONDS", "300"))

_store = {}
_locks = {}
_guard = threading.Lock()


def cached(key: str, compute, ttl: int = None):
    """Return compute() for key, reusing a result younger than ttl seconds.

    Concurrent callers for the same key wait for one computation instead of
    each running it. Exceptions are not cached. The cache is per process
    (each worker keeps its own copy)."""
    ttl = DASHBOARD_CACHE_TTL_SECONDS if ttl is None else ttl
    if ttl <= 0:
        return compute()

    hit = _store.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]

    with _guard:
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        hit = _store.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        value = compute()
        _store[key] = (time.monotonic() + ttl, value)
        return value
