import json
from pathlib import Path
from urllib.request import Request, urlopen


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
