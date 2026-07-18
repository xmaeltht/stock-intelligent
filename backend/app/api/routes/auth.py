import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE, get_current_user
from app.core.config import get_settings
from app.core.security import create_session_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserRead
from app.services.google_oauth import OAuthError, build_auth_url, exchange_code

router = APIRouter()

OAUTH_STATE_COOKIE = "si_oauth_state"


def _issue_session(response: Response, user: User) -> None:
    settings = get_settings()
    token = create_session_token(
        str(user.id), settings.session_secret, settings.session_ttl_hours * 3600
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    existing = db.scalar(select(User).where(func.lower(User.email) == payload.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _issue_session(response, user)
    return user


@router.post("/login", response_model=UserRead)
def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email))
    # Constant-ish work whether or not the user exists, to avoid leaking existence.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    _issue_session(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserRead)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.get("/providers", response_model=dict)
def providers() -> dict:
    return {"google": get_settings().google_enabled}


@router.get("/google/start")
def google_start() -> RedirectResponse:
    settings = get_settings()
    if not settings.google_enabled:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    state = secrets.token_urlsafe(24)
    url = build_auth_url(settings.google_client_id, settings.google_redirect_uri, state)
    response = RedirectResponse(url, status_code=302)
    # Short-lived CSRF state; lax so it survives Google's top-level redirect back.
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/google/callback")
def google_callback(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    base = settings.app_base_url.rstrip("/")
    expected = request.cookies.get(OAUTH_STATE_COOKIE)
    if not settings.google_enabled or not code or not state or state != expected:
        return RedirectResponse(f"{base}/login?error=google", status_code=302)
    try:
        info = exchange_code(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            code=code,
            redirect_uri=settings.google_redirect_uri,
        )
    except OAuthError:
        return RedirectResponse(f"{base}/login?error=google", status_code=302)

    email = info["email"].strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        user = User(
            email=email,
            # Unusable password — this account signs in with Google.
            password_hash=hash_password(secrets.token_urlsafe(32)),
            display_name=info.get("name"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    response = RedirectResponse(f"{base}/", status_code=302)
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    _issue_session(response, user)
    return response
