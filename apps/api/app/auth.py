import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError
from sqlalchemy import func, select
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
MAX_FAILED_LOGINS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class SessionClaims:
    user_id: uuid.UUID
    session_version: int
    token_id: uuid.UUID


def validate_password_strength(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    if len(password) > 1024:
        raise ValueError("Password must not exceed 1024 characters")


def hash_password(password: str) -> str:
    validate_password_strength(password)
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


def create_session_token(user: User | uuid.UUID, session_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    user_id = user.id if isinstance(user, User) else user
    version = int(getattr(user, "session_version", session_version) or 0)
    payload = {
        "sub": str(user_id),
        "ver": version,
        "iat": now,
        "exp": now + session_duration(),
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def decode_session_token(token: str) -> SessionClaims:
    try:
        payload = jwt.decode(
            token,
            _secret_key(),
            algorithms=[ALGORITHM],
            audience=TOKEN_AUDIENCE,
            issuer=TOKEN_ISSUER,
            options={
                "require": ["sub", "ver", "iat", "exp", "iss", "aud", "jti"]
            },
        )
        version = payload["ver"]
        if not isinstance(version, int) or version < 0:
            raise ValueError("Invalid session version")
        return SessionClaims(
            user_id=uuid.UUID(payload["sub"]),
            session_version=version,
            token_id=uuid.UUID(payload["jti"]),
        )
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
    user = db.scalar(
        select(User)
        .where(func.lower(User.email) == normalized_email)
        .with_for_update()
    )
    stored_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    valid_password = verify_password(password, stored_hash)
    if user is None:
        return None
    now = datetime.now(timezone.utc)
    locked_until = getattr(user, "locked_until", None)
    if locked_until is not None and locked_until > now:
        return None
    if not valid_password:
        user.failed_login_count = int(getattr(user, "failed_login_count", 0) or 0) + 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.locked_until = now + LOCKOUT_DURATION
        return None
    if getattr(user, "is_active", True) is False:
        return None
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
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
    claims = decode_session_token(token)
    user = db.scalar(select(User).where(User.id == claims.user_id))
    if (
        user is None
        or getattr(user, "is_active", True) is False
        or int(getattr(user, "session_version", 0) or 0) != claims.session_version
    ):
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
