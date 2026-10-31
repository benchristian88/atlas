"""One-time root enrollment after separately auditing deployment isolation."""
import argparse
import json
from pathlib import Path

from app.services import connector_lifecycle as lifecycle, local_release_authority as authority
from app.services.connector_contracts import strict_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--isolation-report", type=Path)
    selection.add_argument("--inspect-resources", action="store_true", help="Observe resources before human isolation inspection; grants no authority")
    args = parser.parse_args()
    authority.operator()
    from app.database import SessionLocal
    with SessionLocal() as db:
        if args.inspect_resources:
            import time
            observed = authority.inspect_resources(db, lifecycle.package_store().root)
            print(json.dumps({"deployment": observed["deployment"]["name"], "checked_at": int(time.time()),
                "resources": observed, "checks": {key: False for key in sorted(authority.ISOLATION_CHECKS)}}))
            return
        report = strict_json(authority.protected(args.isolation_report, 16 * 1024))
        result = authority.provision(db, lifecycle.package_store().root, report)
        from app.audit import add_audit_event
        add_audit_event(db, action="connector.local_release_instance_bound", target_type="connector_package",
            summary="Root operator enrolled an isolated instance", metadata={"instance_id": result["instance_id"], "authority": "local-root-operator"})
        db.commit()
    print(json.dumps({"state": "bound", "instance_id": result["instance_id"]}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("local_release_enrollment_failed") from None
