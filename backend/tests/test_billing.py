import time
from datetime import UTC, datetime, timedelta

import pytest

from app.core.entitlements import is_pro
from app.models.user import User
from app.services.stripe_client import StripeError, sign_payload, verify_webhook


def _user(plan="free", expires=None) -> User:
    return User(email="a@b.com", password_hash="x", plan=plan, plan_expires_at=expires)


def test_is_pro_states() -> None:
    assert is_pro(_user("pro")) is True
    assert is_pro(_user("free")) is False
    assert is_pro(_user("pro", datetime.now(UTC) + timedelta(days=5))) is True
    assert is_pro(_user("pro", datetime.now(UTC) - timedelta(days=1))) is False


def test_webhook_sign_and_verify_roundtrip() -> None:
    secret = "whsec_test"
    payload = b'{"type":"checkout.session.completed","data":{"object":{}}}'
    header = sign_payload(payload, secret, int(time.time()))
    event = verify_webhook(payload, header, secret)
    assert event["type"] == "checkout.session.completed"


def test_webhook_rejects_tampered_payload() -> None:
    secret = "whsec_test"
    header = sign_payload(b'{"amount":10}', secret, int(time.time()))
    with pytest.raises(StripeError):
        verify_webhook(b'{"amount":1000000}', header, secret)


def test_webhook_rejects_wrong_secret() -> None:
    header = sign_payload(b"{}", "whsec_a", int(time.time()))
    with pytest.raises(StripeError):
        verify_webhook(b"{}", header, "whsec_b")


def test_webhook_rejects_stale_timestamp() -> None:
    secret = "whsec_test"
    header = sign_payload(b"{}", secret, int(time.time()) - 10_000)
    with pytest.raises(StripeError):
        verify_webhook(b"{}", header, secret)
