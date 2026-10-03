from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.auth import (
    COOKIE_NAME,
    CurrentUser,
    authenticate_user,
    cookie_secure,
    create_session_token,
    hash_password,
    session_duration,
    validate_password_strength,
    verify_password,
)
from app.authorization import CurrentPrincipal, _load_principal
from app.database import get_db
from app.models import User
from app.presenters import user_response_data
from app.schemas import (
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    ProfileUpdate,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _set_session_cookie(
    response: Response, user_id, session_version: int
) -> None:
    duration = session_duration()
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_token(user_id, session_version),
        max_age=int(duration.total_seconds()),
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
def login(
    credentials: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    normalized_email = str(credentials.email).strip().lower()
    candidate = db.scalar(select(User).where(User.email == normalized_email))
    user = authenticate_user(db, normalized_email, credentials.password)
    if user is None:
        add_audit_event(
            db,
            action="auth.login_failed",
            target_type="user",
            target_id=candidate.id if candidate is not None else None,
            actor=candidate,
            actor_email=normalized_email,
            success=False,
            summary="Invalid credentials, disabled account, or temporary lockout",
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    add_audit_event(
        db,
        action="auth.login_succeeded",
        target_type="user",
        target_id=user.id,
        actor=user,
        summary="Interactive login succeeded",
        request=request,
    )
    authenticated_version = user.session_version
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, user.id, authenticated_version)
    principal = _load_principal(user, db)
    return LoginResponse(user=UserResponse.model_validate(user_response_data(principal)))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def logout(
    response: Response,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> None:
    # The MVP uses a per-user session generation. Logging out therefore revokes
    # every outstanding browser session for this account, not just this cookie.
    locked_user = db.scalar(
        select(User).where(User.id == user.id).with_for_update()
    )
    if locked_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    locked_user.session_version += 1
    add_audit_event(
        db,
        action="auth.logout",
        target_type="user",
        target_id=locked_user.id,
        actor=locked_user,
        summary="All active sessions were invalidated",
        request=request,
    )
    db.commit()
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


@router.get("/me", response_model=UserResponse)
def current_user(principal: CurrentPrincipal) -> UserResponse:
    return UserResponse.model_validate(user_response_data(principal))


@router.patch("/profile", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdate,
    request: Request,
    principal: CurrentPrincipal,
    db: Session = Depends(get_db),
) -> UserResponse:
    user = principal.user
    previous_name = user.display_name
    previous_accent = user.accent_colour
    previous_theme = user.theme_mode or "system"
    user.display_name = payload.display_name.strip()
    if "accent_colour" in payload.model_fields_set:
        user.accent_colour = payload.accent_colour
    if "theme_mode" in payload.model_fields_set:
        user.theme_mode = payload.theme_mode
    add_audit_event(
        db,
        action="profile.updated",
        target_type="user",
        target_id=user.id,
        actor=user,
        summary="Profile preferences updated",
        metadata={
            "display_name": {"from": previous_name, "to": user.display_name},
            "accent_colour": {"from": previous_accent, "to": user.accent_colour},
            "theme_mode": {"from": previous_theme, "to": user.theme_mode or "system"},
        },
        request=request,
    )
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user_response_data(_load_principal(user, db)))


@router.post("/change-password", response_model=UserResponse)
def change_password(
    payload: PasswordChangeRequest,
    response: Response,
    request: Request,
    principal: CurrentPrincipal,
    db: Session = Depends(get_db),
) -> UserResponse:
    user = db.scalar(
        select(User).where(User.id == principal.user.id).with_for_update()
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not verify_password(payload.current_password, user.password_hash):
        add_audit_event(
            db,
            action="profile.password_change_failed",
            target_type="user",
            target_id=user.id,
            actor=user,
            success=False,
            summary="Current password verification failed",
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    try:
        validate_password_strength(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user.password_hash = hash_password(payload.new_password)
    user.force_password_change = False
    user.failed_login_count = 0
    user.locked_until = None
    user.session_version += 1
    add_audit_event(
        db,
        action="profile.password_changed",
        target_type="user",
        target_id=user.id,
        actor=user,
        summary="Password changed and all other sessions invalidated",
        request=request,
    )
    authenticated_version = user.session_version
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, user.id, authenticated_version)
    return UserResponse.model_validate(user_response_data(_load_principal(user, db)))
