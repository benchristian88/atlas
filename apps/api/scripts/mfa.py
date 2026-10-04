"""Local break-glass recovery, available only to an operator with deployment access."""
import argparse

from sqlalchemy import func, select

from app.audit import add_audit_event
from app.database import SessionLocal
from app.models import User
from app.services.mfa import reset_mfa
from app.services.backup_runtime import normal_operation


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Atlas MFA management")
    parser.add_argument("action", choices=["reset"])
    parser.add_argument("--user", required=True, help="Exact existing account email")
    args = parser.parse_args()
    # Confirmation happens before a transaction takes a row lock. No force flag.
    email = args.user.strip().lower()
    try:
        confirmation = input(f"Reset two-factor authentication for {email}? Type RESET to confirm: ")
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("MFA reset cancelled") from None
    if confirmation != "RESET":
        raise SystemExit("MFA reset cancelled")
    with normal_operation(), SessionLocal.begin() as db:
        matches = list(db.scalars(select(User).where(func.lower(User.email) == email)
                                  .with_for_update().execution_options(populate_existing=True)))
        if len(matches) != 1:
            raise SystemExit("Exactly one existing account must match; MFA was not changed")
        user = matches[0]
        reset_mfa(db, user)
        add_audit_event(db, action="auth.mfa_local_reset", target_type="user", target_id=user.id,
                        actor_email="local-operator", summary="Local operator reset MFA and invalidated sessions; password unchanged")
    print("Two-factor authentication reset. Existing sessions invalidated. Password unchanged.")


if __name__ == "__main__":
    main()
