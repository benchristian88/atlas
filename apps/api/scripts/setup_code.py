"""Local operator tool. No HTTP reset endpoint and no initialized override."""
import argparse
import ipaddress
from urllib.parse import urlsplit

from fastapi import HTTPException

from app.audit import add_audit_event
from app.database import SessionLocal
from app.services.installation import reset_setup_code
from app.services.backup_runtime import normal_operation
from app.services.backup_archive import BackupError


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the one-time Atlas setup code")
    parser.add_argument("action", choices=["reset"])
    parser.add_argument("--access-url", help="Installer's actual non-secret browser URL")
    args = parser.parse_args()
    try:
        with normal_operation(), SessionLocal.begin() as db:
            code = reset_setup_code(db)
            add_audit_event(db, action="setup.code_reset", target_type="installation",
                            summary="Local operator replaced the setup verifier")
    except BackupError as exc:
        raise SystemExit(str(exc)) from None
    except HTTPException as exc:
        if exc.status_code == 409:
            raise SystemExit("Atlas has already been initialised.\nThe setup code cannot be reset on an initialised instance.") from None
        raise SystemExit(exc.detail) from None
    print("Atlas is ready.\n")
    if args.access_url:
        print(f"Open Atlas in your browser:\n\n    {args.access_url}\n")
        address = ipaddress.ip_address(urlsplit(args.access_url).hostname)
        if address.is_loopback:
            print("This URL is local-only. Configure ATLAS_BIND_ADDRESS for LAN access.\n")
        elif address.is_unspecified:
            print("Listening on all interfaces. Use the Atlas host's LAN address in your browser.\n")
    print("Enter this one-time setup code:\n")
    print(f"    {code}\n")
    print("The code is required only until Atlas has been initialised.")


if __name__ == "__main__":
    main()
