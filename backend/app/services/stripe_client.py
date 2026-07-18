"""Minimal Stripe client built on the standard library.

Avoids the stripe SDK dependency. Only what we need: create a Checkout Session
and verify webhook signatures (pure HMAC, unit-testable offline).
"""

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request

STRIPE_API = "https://api.stripe.com/v1"


class StripeError(Exception):
    pass


def create_checkout_session(
    *,
    secret_key: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    client_reference_id: str,
    customer_email: str | None = None,
    customer_id: str | None = None,
) -> dict:
    params = {
        "mode": "subscription",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": client_reference_id,
        "allow_promotion_codes": "true",
    }
    if customer_id:
        params["customer"] = customer_id
    elif customer_email:
        params["customer_email"] = customer_email
    data = urllib.parse.urlencode(params).encode()
    request = urllib.request.Request(
        f"{STRIPE_API}/checkout/sessions",
        data=data,
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:  # noqa: PERF203
        raise StripeError(exc.read().decode()[:300]) from exc
    except Exception as exc:  # noqa: BLE001 - surface any transport failure uniformly
        raise StripeError(str(exc)) from exc


def verify_webhook(payload: bytes, sig_header: str, secret: str, tolerance: int = 300) -> dict:
    """Validate the Stripe-Signature header and return the parsed event."""
    if not sig_header:
        raise StripeError("Missing signature header")
    parts = dict(item.split("=", 1) for item in sig_header.split(",") if "=" in item)
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        raise StripeError("Malformed signature header")
    signed_payload = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise StripeError("Signature mismatch")
    try:
        if abs(int(time.time()) - int(timestamp)) > tolerance:
            raise StripeError("Timestamp outside tolerance")
    except ValueError as exc:
        raise StripeError("Bad timestamp") from exc
    return json.loads(payload)


def sign_payload(payload: bytes, secret: str, timestamp: int) -> str:
    """Build a Stripe-Signature header value (used by tests and local tooling)."""
    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"
