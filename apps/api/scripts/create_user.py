import argparse
import getpass

from sqlalchemy import select

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an Atlas user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    args = parser.parse_args()

    email = args.email.strip().lower()
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")

    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            raise SystemExit("A user with that email already exists")
        db.add(
            User(
                email=email,
                display_name=args.display_name.strip(),
                password_hash=hash_password(password),
            )
        )
    print(f"Created Atlas user {email}")


if __name__ == "__main__":
    main()
