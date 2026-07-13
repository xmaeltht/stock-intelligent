import json
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen


class RateLimiter:
    """Thread-safe minimum interval between calls to one upstream provider.

    The analyzer runs symbols concurrently; without a shared limiter each
    worker would throttle only itself and the combined request rate would
    trip the provider's abuse detection again.
    """

    def __init__(self, min_interval_seconds: float):
        self.min_interval = min_interval_seconds
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._next_allowed - now
            self._next_allowed = max(now, self._next_allowed) + self.min_interval
        if delay > 0:
            time.sleep(delay)


def fetch_bytes(url: str, user_agent: str, timeout: int = 30) -> bytes:
    request = Request(
        url,
        headers={"User-Agent": user_agent, "Accept-Encoding": "identity"},
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - provider URLs are fixed
        return response.read()


def fetch_json(url: str, user_agent: str, cache_path: Path | None = None) -> dict:
    payload = fetch_bytes(url, user_agent)
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(payload)
    return json.loads(payload)
