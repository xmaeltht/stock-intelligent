from app.core.cache import TTLCache, cached, clear_cache


def test_ttl_cache_serves_within_window_and_recomputes_after() -> None:
    cache = TTLCache()
    calls = {"n": 0}

    def producer() -> int:
        calls["n"] += 1
        return calls["n"]

    # First call computes; second within TTL is served from cache.
    assert cache.get_or_set("k", 100.0, producer) == 1
    assert cache.get_or_set("k", 100.0, producer) == 1
    assert calls["n"] == 1

    # A zero TTL entry is always stale, so the producer runs again.
    assert cache.get_or_set("z", 0.0, producer) == 2
    assert cache.get_or_set("z", 0.0, producer) == 3


def test_distinct_keys_are_isolated() -> None:
    cache = TTLCache()
    assert cache.get_or_set("a", 100.0, lambda: "A") == "A"
    assert cache.get_or_set("b", 100.0, lambda: "B") == "B"
    assert cache.get_or_set("a", 100.0, lambda: "changed") == "A"


def test_clear_drops_entries() -> None:
    calls = {"n": 0}

    def producer() -> int:
        calls["n"] += 1
        return calls["n"]

    assert cached("shared", 100.0, producer) == 1
    assert cached("shared", 100.0, producer) == 1
    clear_cache()
    assert cached("shared", 100.0, producer) == 2
