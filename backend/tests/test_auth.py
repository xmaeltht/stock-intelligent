"""Auth flow checks against an in-memory database."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import (
    create_session_token,
    hash_password,
    read_session_token,
    verify_password,
)
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    # https base_url so the Secure session cookie is retained by the test client.
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


def test_password_hash_roundtrip() -> None:
    stored = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", stored)
    assert not verify_password("wrong", stored)
    assert stored != hash_password("correct horse battery staple")  # salted


def test_session_token_roundtrip() -> None:
    token = create_session_token("user-123", "secret", 3600)
    assert read_session_token(token, "secret") == "user-123"
    assert read_session_token(token, "other-secret") is None
    assert read_session_token("garbage", "secret") is None
    assert read_session_token(create_session_token("u", "secret", -1), "secret") is None


def test_register_login_me_logout(client: TestClient) -> None:
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "Investor@Example.com", "password": "supersecret1", "display_name": "Pat"},
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    assert body["email"] == "investor@example.com"  # normalized lowercase
    assert body["display_name"] == "Pat"

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "investor@example.com"

    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_duplicate_email_rejected(client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": "supersecret1"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    again = client.post("/api/v1/auth/register", json={**payload, "email": "DUP@example.com"})
    assert again.status_code == 409


def test_login_wrong_password(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json={"email": "a@b.com", "password": "supersecret1"})
    client.post("/api/v1/auth/logout")
    bad = client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "nope"})
    assert bad.status_code == 401
    good = client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "supersecret1"})
    assert good.status_code == 200


def test_me_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_short_password_rejected(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/register", json={"email": "x@y.com", "password": "short"})
    assert resp.status_code == 422
