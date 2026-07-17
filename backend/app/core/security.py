"""Password hashing and signed session tokens using only the standard library.

Avoiding bcrypt/passlib/pyjwt keeps the slim runtime image reliable and the test
suite dependency-free. PBKDF2-HMAC-SHA256 is a sound password KDF, and a compact
HMAC-signed token gives us stateless sessions without a JWT library.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

_PBKDF2_ITERATIONS = 240_000
_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    """Return a self-describing hash string: algo$iterations$salt$hash (all hex/b64)."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{_ALGO}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != _ALGO:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_session_token(user_id: str, secret: str, ttl_seconds: int) -> str:
    """Compact signed token: <payload_b64>.<hmac_b64> where payload = {uid, exp}."""
    payload = {"uid": user_id, "exp": int(time.time()) + ttl_seconds}
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64url(signature)}"


def read_session_token(token: str, secret: str) -> str | None:
    """Return the user id if the token's signature is valid and it hasn't expired."""
    try:
        payload_b64, signature_b64 = token.split(".")
    except (ValueError, AttributeError):
        return None
    expected = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).digest()
    try:
        if not hmac.compare_digest(expected, _b64url_decode(signature_b64)):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or int(payload.get("exp", 0)) < int(time.time()):
        return None
    uid = payload.get("uid")
    return uid if isinstance(uid, str) else None
