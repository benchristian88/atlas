from fastapi import APIRouter

from app.auth import CurrentUser

router = APIRouter(prefix="/protected", tags=["protected"])


@router.get("")
def protected_example(user: CurrentUser) -> dict[str, str]:
    """Demonstrate the dependency used to protect future API routes."""
    return {"message": f"Authenticated as {user.email}"}
