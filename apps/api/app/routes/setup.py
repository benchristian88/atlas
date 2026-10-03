from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.auth import cookie_secure
from app.database import get_db
from app.schemas import _trim_nonempty
from app.services.installation import SETUP_COOKIE, SETUP_COOKIE_PATH, SETUP_DURATION, create_first_administrator, installation_state, is_initialized, require_setup_authorization, verify_setup_code

router = APIRouter(prefix="/setup", tags=["first-run setup"])


class SetupCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    code: str = Field(min_length=1, max_length=128)


class FirstAdministratorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    display_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=1024)
    password_confirmation: str = Field(min_length=12, max_length=1024)
    _name = field_validator("display_name")(_trim_nonempty)

    @model_validator(mode="after")
    def matching_passwords(self):
        if self.password != self.password_confirmation:
            raise ValueError("Passwords do not match")
        return self


@router.get("/status")
def setup_status(response: Response, token: Annotated[str | None, Cookie(alias=SETUP_COOKIE)] = None, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    state = installation_state(db)
    initialized = is_initialized(db, state)
    authorized = False
    if not initialized:
        from fastapi import HTTPException
        try:
            require_setup_authorization(state, token)
            authorized = True
        except HTTPException:
            pass
    return {"state": "INITIALISED" if initialized else "UNINITIALISED", "authorized": authorized}


@router.post("/verify", status_code=204)
def verify_code(payload: SetupCodeRequest, response: Response, request: Request, db: Session = Depends(get_db)):
    token = verify_setup_code(db, payload.code)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(SETUP_COOKIE, token, max_age=int(SETUP_DURATION.total_seconds()),
                        httponly=True, secure=cookie_secure(request), samesite="lax", path=SETUP_COOKIE_PATH)


@router.post("/administrator", status_code=204)
def create_administrator(payload: FirstAdministratorRequest, response: Response, request: Request,
                         token: Annotated[str | None, Cookie(alias=SETUP_COOKIE)] = None,
                         db: Session = Depends(get_db)):
    user = create_first_administrator(db, payload, token)
    add_audit_event(db, action="setup.initialized", target_type="user", target_id=user.id,
                    actor=user, summary="First Master Administrator created; Atlas initialised", request=request)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    response.delete_cookie(SETUP_COOKIE, path=SETUP_COOKIE_PATH, httponly=True,
                           secure=cookie_secure(request), samesite="lax")
