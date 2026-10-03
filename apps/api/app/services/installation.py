"""First-run state and setup authorization, owned by PostgreSQL."""
from datetime import datetime, timedelta, timezone
import secrets
import uuid

import jwt
from fastapi import HTTPException
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import ALGORITHM, DUMMY_PASSWORD_HASH, LOCKOUT_DURATION, MAX_FAILED_LOGINS, TOKEN_ISSUER, _secret_key, hash_password, password_hasher, verify_password
from app.models import InstallationState, User

SETUP_COOKIE = "atlas_setup"
SETUP_COOKIE_PATH = "/api/setup"
SETUP_AUDIENCE = "atlas-setup"
SETUP_DURATION = timedelta(minutes=10)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def installation_state(db: Session, *, lock: bool = False) -> InstallationState:
    statement = select(InstallationState).where(InstallationState.id == 1)
    if lock:
        statement = statement.with_for_update()
    state = db.scalar(statement)
    if state is None:
        raise HTTPException(status_code=503, detail="Atlas initialization state is unavailable")
    return state


def is_initialized(db: Session, state: InstallationState) -> bool:
    return state.initialized_at is not None or db.scalar(select(User.id).limit(1)) is not None


def require_uninitialized(db: Session, state: InstallationState) -> None:
    if is_initialized(db, state):
        raise HTTPException(status_code=409, detail="Atlas has already been initialised")


def normalize_code(code: str) -> str:
    return code.replace("-", "").replace(" ", "").upper()


def reset_setup_code(db: Session) -> str:
    state = installation_state(db, lock=True)
    require_uninitialized(db, state)
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(20))
    state.setup_code_hash = password_hasher.hash(raw)
    state.setup_generation += 1
    state.failed_attempts = 0
    state.locked_until = None
    db.flush()
    return "-".join(raw[i:i + 4] for i in range(0, 20, 4))


def verify_setup_code(db: Session, code: str) -> str:
    state = installation_state(db, lock=True)
    require_uninitialized(db, state)
    now = datetime.now(timezone.utc)
    if state.locked_until is not None and state.locked_until > now:
        raise HTTPException(status_code=429, detail="Setup verification temporarily unavailable. Try again later.")
    valid = verify_password(normalize_code(code), state.setup_code_hash or DUMMY_PASSWORD_HASH)
    if not valid or state.setup_code_hash is None:
        state.failed_attempts += 1
        if state.failed_attempts >= MAX_FAILED_LOGINS:
            state.locked_until = now + LOCKOUT_DURATION
            state.failed_attempts = 0
        # Failed attempts must persist even though the API returns an error.
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid setup code")
    state.failed_attempts = 0
    state.locked_until = None
    return jwt.encode({
        "sub": "installation-setup", "generation": state.setup_generation,
        "iat": now, "exp": now + SETUP_DURATION, "jti": str(uuid.uuid4()),
        "iss": TOKEN_ISSUER, "aud": SETUP_AUDIENCE,
    }, _secret_key(), algorithm=ALGORITHM)


def require_setup_authorization(state: InstallationState, token: str | None) -> None:
    try:
        payload = jwt.decode(
            token or "", _secret_key(), algorithms=[ALGORITHM],
            issuer=TOKEN_ISSUER, audience=SETUP_AUDIENCE,
            options={"require": ["sub", "generation", "iat", "exp", "iss", "aud", "jti"]},
        )
        if (payload["sub"] != "installation-setup"
            or type(payload["generation"]) is not int
            or payload["generation"] != state.setup_generation
            or state.setup_code_hash is None):
            raise ValueError("Invalid setup generation")
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Setup authorization required") from exc


def create_first_administrator(db: Session, payload, token: str | None) -> User:
    # The same singleton lock guards creation, reset and verification. The
    # caller commits user, RBAC, context, audit and state in one transaction.
    state = installation_state(db, lock=True)
    require_uninitialized(db, state)
    require_setup_authorization(state, token)
    from scripts.seed_system import _ensure_rbac, _ensure_home_context
    from app.models import AccessAssignment

    master = _ensure_rbac(db)
    _ensure_home_context(db)
    user = User(
        email=str(payload.email).strip().lower(), display_name=payload.display_name,
        password_hash=hash_password(payload.password), is_active=True,
        force_password_change=False, auth_provider="local", mfa_enabled=False,
    )
    db.add(user)
    db.flush()
    db.add(AccessAssignment(user_id=user.id, role_id=master.id, scope_type="global"))
    state.initialized_at = datetime.now(timezone.utc)
    state.setup_code_hash = None
    state.setup_generation += 1
    state.failed_attempts = 0
    state.locked_until = None
    db.flush()
    return user
