from fastapi import APIRouter

from app.authorization import CurrentPrincipal, forbidden

router = APIRouter(prefix="/protected", tags=["protected"])


@router.get("")
def protected_example(principal: CurrentPrincipal) -> dict[str, str]:
    """Demonstrate the dependency used to protect future API routes."""
    if principal.user.force_password_change:
        raise forbidden("You must change your password before continuing")
    return {"message": f"Authenticated as {principal.user.email}"}
