"""Account-owned MFA contracts; scoped login cookies confer no application access."""
from datetime import datetime
from typing import Literal
import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import CurrentUser, cookie_secure
from app.authorization import _load_principal
from app.database import get_db
from app.presenters import user_response_data
from app.routes.auth import _set_session_cookie
from app.schemas import LoginResponse, UserResponse
from app.services import mfa

router = APIRouter(prefix="/auth/mfa", tags=["two-factor authentication"])


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    current_password: str = Field(min_length=1, max_length=1024, repr=False)
    code: str | None = Field(default=None, max_length=100, repr=False)
    method: Literal["totp", "recovery"] = "totp"


class Verification(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    code: str = Field(min_length=1, max_length=100, repr=False)
    method: Literal["totp", "recovery"] = "totp"


class Confirmation(Verification):
    enrollment_id: uuid.UUID
    method: Literal["totp"] = "totp"


class EnrollmentResponse(BaseModel):
    enrollment_id: uuid.UUID
    manual_key: str = Field(repr=False)
    otpauth_uri: str = Field(repr=False)
    expires_at: datetime


class RecoveryResponse(BaseModel):
    recovery_codes: list[str] = Field(repr=False)


class StatusResponse(BaseModel):
    enabled: bool
    confirmed_at: datetime | None
    recovery_codes_remaining: int
    recovery_codes_total: int


def account(db, current):
    return mfa.locked_user(db, current.id, current.session_version)


def clear_challenge_cookie(response: Response, request: Request):
    response.delete_cookie(mfa.MFA_COOKIE, path=mfa.MFA_COOKIE_PATH, httponly=True,
                           secure=cookie_secure(request), samesite="lax")


@router.get("/status", response_model=StatusResponse)
def status(user: CurrentUser, db: Session = Depends(get_db)):
    return mfa.mfa_status(db, user)


@router.post("/enrollment", response_model=EnrollmentResponse)
def enroll(payload: Credentials, request: Request, current: CurrentUser, db: Session = Depends(get_db)):
    user = account(db, current)
    result = mfa.begin_enrollment(db, user, payload.current_password, payload.code, payload.method, request)
    db.commit()
    return result


@router.delete("/enrollment", status_code=204)
def cancel_enrollment(current: CurrentUser, db: Session = Depends(get_db)):
    user = account(db, current)
    state = mfa.state_for(db, user)
    if state is not None:
        mfa.clear_pending(state)
    db.commit()


@router.post("/enrollment/confirm", response_model=RecoveryResponse)
def confirm(payload: Confirmation, request: Request, response: Response, current: CurrentUser,
            db: Session = Depends(get_db)):
    user = account(db, current)
    if user.force_password_change:
        raise HTTPException(403, "You must change your password before continuing")
    codes = mfa.confirm_enrollment(db, user, payload.enrollment_id, payload.code, request)
    version = user.session_version
    db.commit()
    _set_session_cookie(response, user.id, version, db, request)
    clear_challenge_cookie(response, request)
    return {"recovery_codes": codes}


@router.post("/verify", response_model=LoginResponse)
def verify(payload: Verification, request: Request, response: Response,
           challenge: str | None = Cookie(default=None, alias=mfa.MFA_COOKIE), db: Session = Depends(get_db)):
    user = mfa.complete_challenge(db, challenge, payload.code, payload.method, request)
    version = user.session_version
    db.commit()
    _set_session_cookie(response, user.id, version, db, request)
    clear_challenge_cookie(response, request)
    return LoginResponse(user=UserResponse.model_validate(user_response_data(_load_principal(user, db))))


@router.post("/cancel", status_code=204)
def cancel(request: Request, response: Response,
           challenge: str | None = Cookie(default=None, alias=mfa.MFA_COOKIE), db: Session = Depends(get_db)):
    # Revocation needs no factor; only the holder can revoke its exact attempt.
    import jwt
    from jwt.exceptions import InvalidTokenError
    from app.auth import ALGORITHM, TOKEN_ISSUER, _secret_key
    from app.models import MfaChallenge
    from sqlalchemy import delete
    try:
        claims = jwt.decode(challenge or "", _secret_key(), algorithms=[ALGORITHM], audience=mfa.MFA_AUDIENCE, issuer=TOKEN_ISSUER)
        user = mfa.locked_user(db, uuid.UUID(claims["sub"]), claims["ver"])
        db.execute(delete(MfaChallenge).where(MfaChallenge.user_id == user.id, MfaChallenge.id == uuid.UUID(claims["jti"])))
        db.commit()
    except (InvalidTokenError, ValueError, KeyError, TypeError, HTTPException):
        db.rollback()
    clear_challenge_cookie(response, request)


@router.post("/recovery-codes", response_model=RecoveryResponse)
def regenerate(payload: Credentials, current: CurrentUser, request: Request, db: Session = Depends(get_db)):
    user = account(db, current)
    mfa.reauthenticate(db, user, payload.current_password, request)
    if not user.mfa_enabled:
        raise HTTPException(409, "Two-factor authentication is not enabled")
    if payload.method != "totp":
        raise HTTPException(400, "Use a current authenticator code to generate recovery codes")
    state = mfa.state_for(db, user)
    mfa.verify_factor(db, user, state, payload.code or "", "totp", request)
    codes = mfa.new_recovery_codes(db, user)
    mfa.audit(db, user, "auth.mfa_recovery_regenerated", request)
    db.commit()
    return {"recovery_codes": codes}


@router.post("/disable", status_code=204)
def disable(payload: Credentials, current: CurrentUser, request: Request, response: Response,
            db: Session = Depends(get_db)):
    user = account(db, current)
    mfa.reauthenticate(db, user, payload.current_password, request)
    if not user.mfa_enabled:
        raise HTTPException(409, "Two-factor authentication is not enabled")
    mfa.verify_factor(db, user, mfa.state_for(db, user), payload.code or "", payload.method, request)
    mfa.reset_mfa(db, user)
    mfa.audit(db, user, "auth.mfa_disabled", request)
    version = user.session_version
    db.commit()
    _set_session_cookie(response, user.id, version, db, request)
    clear_challenge_cookie(response, request)
