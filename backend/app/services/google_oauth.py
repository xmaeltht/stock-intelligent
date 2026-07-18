"""Google OAuth (authorization code flow) using the standard library."""

import json
import urllib.error
import urllib.parse
import urllib.request

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class OAuthError(Exception):
    pass


def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def _post_json(url: str, data: bytes | None, headers: dict) -> dict:
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise OAuthError(exc.read().decode()[:300]) from exc
    except Exception as exc:  # noqa: BLE001 - uniform transport failure
        raise OAuthError(str(exc)) from exc


def exchange_code(*, client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    """Exchange an auth code for tokens, then return the Google userinfo dict."""
    data = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode()
    tokens = _post_json(
        TOKEN_URL, data, {"Content-Type": "application/x-www-form-urlencoded"}
    )
    access_token = tokens.get("access_token")
    if not access_token:
        raise OAuthError("Google did not return an access token")
    info = _post_json(USERINFO_URL, None, {"Authorization": f"Bearer {access_token}"})
    if not info.get("email"):
        raise OAuthError("Google account has no email")
    return info
