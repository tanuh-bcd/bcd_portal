import threading
import time

from backend.src.core import cache


def setup_function():
    cache._store.clear()
    cache._locks.clear()


def test_result_is_reused_within_ttl():
    calls = []
    compute = lambda: calls.append(1) or len(calls)
    assert cache.cached("k", compute, ttl=60) == 1
    assert cache.cached("k", compute, ttl=60) == 1
    assert len(calls) == 1


def test_ttl_zero_disables_caching():
    calls = []
    compute = lambda: calls.append(1) or len(calls)
    assert cache.cached("k", compute, ttl=0) == 1
    assert cache.cached("k", compute, ttl=0) == 2


def test_expired_result_is_recomputed():
    calls = []
    compute = lambda: calls.append(1) or len(calls)
    cache.cached("k", compute, ttl=0.05)
    time.sleep(0.1)
    assert cache.cached("k", compute, ttl=0.05) == 2


def test_exception_is_not_cached():
    def boom():
        raise RuntimeError("db down")

    try:
        cache.cached("k", boom, ttl=60)
    except RuntimeError:
        pass
    assert cache.cached("k", lambda: "ok", ttl=60) == "ok"


def test_concurrent_callers_compute_once():
    calls = []

    def slow():
        calls.append(1)
        time.sleep(0.2)
        return "value"

    results = []
    threads = [threading.Thread(target=lambda: results.append(cache.cached("k", slow, ttl=60))) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == ["value"] * 5
    assert len(calls) == 1
