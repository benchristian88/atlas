"""Local operator tool. No HTTP reset endpoint and no initialized override."""
import argparse

from fastapi import HTTPException

from app.audit import add_audit_event
from app.database import SessionLocal
from app.services.installation import reset_setup_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the one-time Atlas setup code")
    parser.add_argument("action", choices=["reset"])
    parser.parse_args()
    try:
        with SessionLocal.begin() as db:
            code = reset_setup_code(db)
            add_audit_event(db, action="setup.code_reset", target_type="installation",
                            summary="Local operator replaced the setup verifier")
    except HTTPException as exc:
        if exc.status_code == 409:
            raise SystemExit("Atlas has already been initialised.\nThe setup code cannot be reset on an initialised instance.") from None
        raise SystemExit(exc.detail) from None
    print("Atlas is ready.\n\nOpen Atlas in your browser and enter this one-time setup code:\n")
    print(f"    {code}\n")
    print("The code is required only until Atlas has been initialised.")


if __name__ == "__main__":
    main()
