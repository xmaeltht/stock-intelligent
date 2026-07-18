"""Tiny thread-safe in-process TTL cache for expensive, universe-wide reads.

The dashboard summary, discovery radar, and idea lists are computed by scanning
the latest analysis of the *entire* security universe and pulling large JSON
columns. They change only when the analyzer re-rates or the live price loop
advances, so serving them from a short-lived cache removes repeated full-table
scans with no perceptible staleness. The backend runs a single replica, so a
process-local cache is authoritative.

The producer is intentionally called outside the lock: a cold miss should not
serialize every other request behind one slow scan. Concurrent misses may each
compute once (a brief dogpile), which is correct — just not deduplicated.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get_or_set[T](self, key: str, ttl: float, producer: Callable[[], T]) -> T:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is not None and entry[0] > now:
                return entry[1]  # type: ignore[return-value]
        value = producer()
        with self._lock:
            self._store[key] = (now + ttl, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_cache = TTLCache()


def cached[T](key: str, ttl: float, producer: Callable[[], T]) -> T:
    """Return a cached value for ``key`` or compute and store it for ``ttl`` seconds."""
    return _cache.get_or_set(key, ttl, producer)


def clear_cache() -> None:
    """Drop all cached entries (used by tests to guarantee isolation)."""
    _cache.clear()
