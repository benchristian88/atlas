"""Local MFA. All credential mutations serialize on the existing User row.

Callers commit the credential, challenge/session generation and audit together.
Failure counters deliberately commit before returning an authentication error.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException, Request
import jwt
from jwt.exceptions import InvalidTokenError
import pyotp
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.auth import ALGORITHM, LOCKOUT_DURATION, MAX_FAILED_LOGINS, TOKEN_ISSUER, _secret_key, verify_password
from app.config import data_encryption_key
from app.models import MfaChallenge, MfaRecoveryCode, User, UserMfa

MFA_COOKIE = "atlas_mfa"
MFA_COOKIE_PATH = "/api/auth/mfa"
MFA_AUDIENCE = "atlas-mfa-login"
CHALLENGE_DURATION = timedelta(minutes=5)
ENROLLMENT_DURATION = timedelta(minutes=10)
RECOVERY_COUNT = 12
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def now() -> datetime:
    return datetime.now(timezone.utc)


def encrypt_seed(user_id: uuid.UUID, seed: str) -> tuple[bytes, bytes]:
    try:
        key = data_encryption_key()
    except RuntimeError:
        raise HTTPException(503, "MFA data encryption is not configured; contact the local operator") from None
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(nonce, seed.encode("ascii"), f"atlas-mfa:v1:{user_id}".encode())
    return nonce, ciphertext


def decrypt_seed(user_id: uuid.UUID, nonce: bytes, ciphertext: bytes, version: int = 1) -> str:
    if version != 1:
        raise HTTPException(503, "Two-factor authentication material is unavailable; contact the local operator")
    try:
        return AESGCM(data_encryption_key()).decrypt(nonce, ciphertext, f"atlas-mfa:v1:{user_id}".encode()).decode("ascii")
    except (InvalidTag, ValueError, UnicodeError):
        # No plaintext, key, nonce or raw crypto exception reaches a client/log.
        raise HTTPException(503, "Two-factor authentication material is unavailable; contact the local operator") from None


def locked_user(db: Session, user_id: uuid.UUID, session_version: int | None = None) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    if user is None or not user.is_active or (session_version is not None and user.session_version != session_version):
        raise HTTPException(401, "Authentication required")
    return user


def state_for(db: Session, user: User) -> UserMfa | None:
    state = db.scalar(select(UserMfa).where(UserMfa.user_id == user.id).execution_options(populate_existing=True))
    # Fail closed on inconsistent restored/corrupt state, never password-only.
    if user.mfa_enabled and (state is None or state.secret_ciphertext is None):
        raise HTTPException(503, "Two-factor authentication material is unavailable; contact the local operator")
    return state


def audit(db, user, action, request=None, *, actor=None, success=True):
    add_audit_event(db, action=action, target_type="user", target_id=user.id,
                    actor=actor or user, success=success, request=request)


def check_lock(state: UserMfa) -> None:
    if state.locked_until is not None and state.locked_until > now():
        raise HTTPException(429, "Two-factor verification temporarily unavailable. Try again later.")


def reauthenticate(db: Session, user: User, password: str, request: Request | None = None) -> None:
    if user.force_password_change:
        raise HTTPException(403, "You must change your password before continuing")
    if user.locked_until is not None and user.locked_until > now():
        raise HTTPException(429, "Password verification temporarily unavailable. Try again later.")
    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.locked_until = now() + LOCKOUT_DURATION
        audit(db, user, "auth.mfa_reauthentication_failed", request, success=False)
        db.commit()
        raise HTTPException(400, "Current password is incorrect")
    user.failed_login_count = 0
    user.locked_until = None


def matching_step(seed: str, code: str, last_step: int | None) -> int | None:
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return None
    current = int(now().timestamp()) // 30
    totp = pyotp.TOTP(seed, digits=6, interval=30)
    matches = [step for step in (current - 1, current, current + 1)
               if totp.verify(code, for_time=step * 30, valid_window=0)]
    # A rare adjacent collision must not turn a replay into an accepted code.
    if not matches or (last_step is not None and min(matches) <= last_step):
        return None
    return max(matches)


def recovery_verifier(user_id: uuid.UUID, code: str) -> str:
    normalized = code.replace("-", "").replace(" ", "").upper()
    return hashlib.sha256(f"atlas-recovery:v1:{user_id}:{normalized}".encode()).hexdigest()


def new_recovery_codes(db: Session, user: User) -> list[str]:
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
    codes = []
    for _ in range(RECOVERY_COUNT):
        raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(24))
        code = "-".join(raw[i:i + 4] for i in range(0, 24, 4))
        db.add(MfaRecoveryCode(user_id=user.id, verifier=recovery_verifier(user.id, code)))
        codes.append(code)
    return codes


def verify_factor(db: Session, user: User, state: UserMfa, code: str, method: str,
                  request: Request | None = None) -> None:
    check_lock(state)
    accepted = False
    if method == "totp":
        seed = decrypt_seed(user.id, state.secret_nonce, state.secret_ciphertext, state.encryption_version)
        step = matching_step(seed, code, state.last_totp_step)
        if step is not None:
            state.last_totp_step = step
            accepted = True
    elif method == "recovery":
        verifier = recovery_verifier(user.id, code)
        # Compare every verifier (including consumed ones) without early exit.
        codes = list(db.scalars(select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id)))
        matched = None
        for item in codes:
            equal = hmac.compare_digest(item.verifier, verifier)
            if equal and item.consumed_at is None:
                matched = item
        if matched is not None:
            matched.consumed_at = now()
            audit(db, user, "auth.mfa_recovery_used", request)
            accepted = True
    if not accepted:
        state.failed_attempts += 1
        if state.failed_attempts >= MAX_FAILED_LOGINS:
            state.locked_until = now() + LOCKOUT_DURATION
            state.failed_attempts = 0
        audit(db, user, "auth.mfa_verification_failed", request, success=False)
        # Caller owns challenge attempts; flush them in this same failure commit.
        db.commit()
        raise HTTPException(400, "Invalid or already used verification code. Use a new code.")
    state.failed_attempts = 0
    state.locked_until = None


def clear_pending(state: UserMfa) -> None:
    state.pending_ciphertext = state.pending_nonce = state.pending_id = state.pending_expires_at = None
    state.pending_attempts = 0


def invalidate_challenges(db: Session, user: User) -> None:
    db.execute(delete(MfaChallenge).where(MfaChallenge.user_id == user.id))


def begin_enrollment(db: Session, user: User, password: str, code: str | None,
                     method: str, request: Request | None = None) -> dict:
    reauthenticate(db, user, password, request)
    state = state_for(db, user)
    if user.mfa_enabled:
        verify_factor(db, user, state, code or "", method, request)
    if state is None:
        state = UserMfa(user_id=user.id, pending_attempts=0, failed_attempts=0)
        db.add(state)
    seed = pyotp.random_base32(length=32)  # 160 cryptographically random bits.
    state.pending_nonce, state.pending_ciphertext = encrypt_seed(user.id, seed)
    state.pending_id = uuid.uuid4()
    state.pending_expires_at = now() + ENROLLMENT_DURATION
    state.pending_attempts = 0
    state.encryption_version = 1
    return {"enrollment_id": state.pending_id, "manual_key": seed,
            "otpauth_uri": pyotp.TOTP(seed).provisioning_uri(name=user.email, issuer_name="Atlas"),
            "expires_at": state.pending_expires_at}


def confirm_enrollment(db: Session, user: User, enrollment_id: uuid.UUID, code: str,
                       request: Request | None = None) -> list[str]:
    state = state_for(db, user)
    if (state is None or state.pending_id != enrollment_id or state.pending_expires_at is None
            or state.pending_expires_at <= now()):
        if state is not None and state.pending_expires_at is not None and state.pending_expires_at <= now():
            clear_pending(state)
            db.commit()
        raise HTTPException(409, "Enrollment has expired or was replaced. Start again.")
    seed = decrypt_seed(user.id, state.pending_nonce, state.pending_ciphertext, state.encryption_version)
    step = matching_step(seed, code, None)
    if step is None:
        state.pending_attempts += 1
        if state.pending_attempts >= MAX_FAILED_LOGINS:
            clear_pending(state)
        audit(db, user, "auth.mfa_enrollment_failed", request, success=False)
        db.commit()
        raise HTTPException(400, "Invalid authenticator code")
    replacing = user.mfa_enabled
    state.secret_nonce, state.secret_ciphertext = state.pending_nonce, state.pending_ciphertext
    state.confirmed_at = now()
    state.last_totp_step = step
    state.failed_attempts = 0
    state.locked_until = None
    clear_pending(state)
    user.mfa_enabled = True
    user.session_version += 1  # Revoke password-only sessions and older attempts.
    invalidate_challenges(db, user)
    db.flush()
    codes = new_recovery_codes(db, user)
    audit(db, user, "auth.mfa_replaced" if replacing else "auth.mfa_enabled", request)
    return codes


def reset_mfa(db: Session, user: User) -> None:
    # Production sessions disable autoflush. Persist a just-consumed recovery
    # verifier before the FK cascade retires its row, in the same transaction.
    db.flush()
    invalidate_challenges(db, user)
    db.execute(delete(UserMfa).where(UserMfa.user_id == user.id))
    user.mfa_enabled = False
    user.session_version += 1


def mfa_status(db: Session, user: User) -> dict:
    state = state_for(db, user)
    remaining = db.scalar(select(func.count()).select_from(MfaRecoveryCode).where(
        MfaRecoveryCode.user_id == user.id, MfaRecoveryCode.consumed_at.is_(None))) if user.mfa_enabled else 0
    return {"enabled": user.mfa_enabled, "confirmed_at": state.confirmed_at if state and user.mfa_enabled else None,
            "recovery_codes_remaining": remaining, "recovery_codes_total": RECOVERY_COUNT}


def create_challenge(db: Session, user: User) -> str:
    state = state_for(db, user)
    check_lock(state)
    invalidate_challenges(db, user)
    identifier = uuid.uuid4()
    issued = now()
    db.add(MfaChallenge(user_id=user.id, id=identifier, session_version=user.session_version,
                        expires_at=issued + CHALLENGE_DURATION, failed_attempts=0))
    return jwt.encode({"sub": str(user.id), "ver": user.session_version, "jti": str(identifier),
                       "iat": issued, "exp": issued + CHALLENGE_DURATION,
                       "iss": TOKEN_ISSUER, "aud": MFA_AUDIENCE}, _secret_key(), algorithm=ALGORITHM)


def complete_challenge(db: Session, token: str | None, code: str, method: str,
                       request: Request | None = None) -> User:
    try:
        claims = jwt.decode(token or "", _secret_key(), algorithms=[ALGORITHM], audience=MFA_AUDIENCE,
                            issuer=TOKEN_ISSUER, options={"require": ["sub", "ver", "jti", "iat", "exp", "iss", "aud"]})
        user_id, identifier = uuid.UUID(claims["sub"]), uuid.UUID(claims["jti"])
        if type(claims["ver"]) is not int:
            raise ValueError()
    except (InvalidTokenError, ValueError, TypeError, KeyError):
        raise HTTPException(401, "Sign in again to verify two-factor authentication") from None
    user = locked_user(db, user_id, claims["ver"])
    challenge = db.scalar(select(MfaChallenge).where(MfaChallenge.user_id == user.id).execution_options(populate_existing=True))
    if (not user.mfa_enabled or challenge is None or challenge.id != identifier
            or challenge.session_version != user.session_version or challenge.expires_at <= now()
            or challenge.failed_attempts >= MAX_FAILED_LOGINS):
        raise HTTPException(401, "Sign in again to verify two-factor authentication")
    state = state_for(db, user)
    # Increment before verification so failed credential and attempt persist together.
    challenge.failed_attempts += 1
    verify_factor(db, user, state, code, method, request)
    invalidate_challenges(db, user)
    user.last_login_at = now()
    audit(db, user, "auth.login_succeeded", request)
    return user
