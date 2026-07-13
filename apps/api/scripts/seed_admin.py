import os
from collections.abc import Mapping

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User

REQUIRED_VARIABLES = (
    "ATLAS_ADMIN_EMAIL",
    "ATLAS_ADMIN_PASSWORD",
    "ATLAS_ADMIN_DISPLAY_NAME",
)


class AdminSeedError(ValueError):
    """Raised when the admin seed configuration is missing or invalid."""


def seed_admin(db: Session, environment: Mapping[str, str]) -> bool:
    missing = [name for name in REQUIRED_VARIABLES if not environment.get(name, "").strip()]
    if missing:
        raise AdminSeedError(
            "Missing required admin seed variables: " + ", ".join(missing)
        )

    raw_email = environment["ATLAS_ADMIN_EMAIL"].strip()
    password = environment["ATLAS_ADMIN_PASSWORD"]
    display_name = environment["ATLAS_ADMIN_DISPLAY_NAME"].strip()
    try:
        email = validate_email(raw_email, check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise AdminSeedError("ATLAS_ADMIN_EMAIL must be a valid email address") from exc
    if len(password) < 12:
        raise AdminSeedError("ATLAS_ADMIN_PASSWORD must contain at least 12 characters")

    if db.scalar(select(User.id).where(User.email == email)) is not None:
        return False

    db.add(
        User(
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
        )
    )
    return True


def main() -> None:
    try:
        with SessionLocal.begin() as db:
            created = seed_admin(db, os.environ)
    except AdminSeedError as exc:
        raise SystemExit(f"Admin seed failed: {exc}") from exc

    email = os.environ["ATLAS_ADMIN_EMAIL"].strip().lower()
    if created:
        print(f"Created Atlas admin user {email}")
    else:
        print(f"Atlas admin user {email} already exists")


if __name__ == "__main__":
    main()
