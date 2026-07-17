"""Shared FastAPI dependencies for authentication."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import read_session_token
from app.db.session import get_db
from app.models.user import User

SESSION_COOKIE = "si_session"


def get_optional_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Return the signed-in user, or None for anonymous visitors (never raises)."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    user_id = read_session_token(token, get_settings().session_secret)
    if not user_id:
        return None
    try:
        return db.get(User, uuid.UUID(user_id))
    except (ValueError, TypeError):  # malformed id must not 500 the request
        return None


def get_current_user(
    user: Annotated[User | None, Depends(get_optional_user)],
) -> User:
    """Require an authenticated user; 401 otherwise."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user
