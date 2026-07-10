from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth import (
    COOKIE_NAME,
    CurrentUser,
    authenticate_user,
    cookie_secure,
    create_session_token,
    session_duration,
)
from app.database import get_db
from app.schemas import LoginRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, str(credentials.email), credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    duration = session_duration()
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_token(user.id),
        max_age=int(duration.total_seconds()),
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )
    return LoginResponse(user=UserResponse.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


@router.get("/me", response_model=UserResponse)
def current_user(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
