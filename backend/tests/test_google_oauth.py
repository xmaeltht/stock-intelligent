from urllib.parse import parse_qs, urlparse

from app.services.google_oauth import build_auth_url


def test_build_auth_url_has_expected_params() -> None:
    url = build_auth_url("client-123", "https://app.example/cb", "state-xyz")
    parsed = urlparse(url)
    assert parsed.netloc == "accounts.google.com"
    query = parse_qs(parsed.query)
    assert query["client_id"] == ["client-123"]
    assert query["redirect_uri"] == ["https://app.example/cb"]
    assert query["state"] == ["state-xyz"]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["openid email profile"]
