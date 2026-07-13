import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

ALGORITHM = "HS256"
COOKIE_NAME = "atlas_session"
TOKEN_ISSUER = "atlas-api"
TOKEN_AUDIENCE = "atlas-web"

password_hasher = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)
# Verifying this hash when an email is unknown keeps failure timing less revealing.
DUMMY_PASSWORD_HASH = password_hasher.hash("atlas-dummy-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except PwdlibError:
        # Treat unrecognized or malformed stored hashes as invalid credentials.
        return False


def _secret_key() -> str:
    secret = os.getenv("AUTH_SECRET_KEY")
    if not secret or len(secret) < 32:
        raise RuntimeError("AUTH_SECRET_KEY must contain at least 32 characters")
    return secret


def session_duration() -> timedelta:
    raw_minutes = os.getenv("AUTH_SESSION_MINUTES", "480")
    try:
        minutes = int(raw_minutes)
    except ValueError as exc:
        raise RuntimeError("AUTH_SESSION_MINUTES must be an integer") from exc
    if not 1 <= minutes <= 10080:
        raise RuntimeError("AUTH_SESSION_MINUTES must be between 1 and 10080")
    return timedelta(minutes=minutes)


def cookie_secure() -> bool:
    return os.getenv("AUTH_COOKIE_SECURE", "true").lower() in {"1", "true", "yes"}


def create_session_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + session_duration(),
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def decode_session_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            _secret_key(),
            algorithms=[ALGORITHM],
            audience=TOKEN_AUDIENCE,
            issuer=TOKEN_ISSUER,
            options={"require": ["sub", "iat", "exp", "iss", "aud", "jti"]},
        )
        return uuid.UUID(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise unauthorized() from exc


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    stored_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    if not verify_password(password, stored_hash) or user is None:
        return None
    return user


def get_current_user(
    bearer: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
    session_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    db: Session = Depends(get_db),
) -> User:
    token = bearer.credentials if bearer is not None else session_token
    if token is None:
        raise unauthorized()
    user_id = decode_session_token(token)
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
