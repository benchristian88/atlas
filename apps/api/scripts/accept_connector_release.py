"""Root operator acceptance of exact signed immutable official releases, locally."""
import argparse
import asyncio
import json
from pathlib import Path
import re

from sqlalchemy.exc import SQLAlchemyError

from app.services import connector_release_acceptance as service
from app.services import connector_lifecycle as lifecycle, local_release_authority as authority
from app.services.connector_contracts import strict_json
from app.services.connector_store import _read_regular


async def run(args):
    if args.action == "verify":
        result = await service.verify_release(selected(args), args.evidence_directory)
        return {"state": "verified_only", "result": result}
    authority.operator()
    root = lifecycle.package_store().root
    if args.action in {"revoke", "recover-revocation"}:
        result = service.revoke(root, args.authorization_id, corrupt_sha256=args.corrupt_sha256)
        return {"state": "revoked", "artifact_id": args.authorization_id, **result}
    if args.action == "reconcile-revocation":
        return service.reconcile_revocation(root, args.authorization_id)
    from app.database import SessionLocal
    from app.services.integration_runtime import runtime
    with SessionLocal() as db:
        if args.action in {"plan-restoration", "authorize-restoration"}:
            from app.services import local_release_restoration as restoration
            authority.require(args.replacement_store is not None and args.connector_id is not None
                and args.version is not None and args.sha256 is not None, "local_release_complete_replacement_required")
            authority.require(not (args.clear_scopes and args.scope), "local_release_invalid_scopes")
            scopes = [] if args.clear_scopes else args.scope
            if args.action == "plan-restoration":
                return restoration.plan(db, root, args.replacement_store, args.connector_id, args.version, args.sha256, scopes=scopes)
            return restoration.authorize(db, root, args.replacement_store, args.connector_id, args.version,
                                         args.sha256, args.approve_plan, scopes=scopes)
        if args.action == "stage":
            stored = await service.stage(db, root, selected(args))
            from app.audit import add_audit_event
            add_audit_event(db, action="connector.local_release_staged", target_type="connector_package",
                summary="Root operator staged an authenticated release without activation", metadata=stored.safe_metadata())
            db.commit()
            return {"state": "staged_only", **stored.safe_metadata()}
        choices = strict_json(_read_regular(args.mappings, 16 * 1024), maximum=16 * 1024) if args.mappings else []
        isolation = strict_json(authority.protected(args.isolation_report, 16 * 1024)) if args.isolation_report else None
        if args.action == "plan":
            with db.begin_nested() as preview:
                result = service.plan(db, root, selected(args), await runtime.health(), choices=choices, scopes=args.scope,
                    isolation=isolation, action=args.operation, lease_seconds=args.lease_seconds)
                preview.rollback()
            db.rollback()
            return {"state": "approval_required", **result}
        authority.require(args.approve_plan is not None, "local_release_explicit_approval_required")
        if args.action in {"renew", "recover"}:
            authority.require(not choices and args.scope is None, "local_release_renewal_cannot_reconfigure")
            active = await service.maintain_execution(db, root, selected(args), args.approve_plan, runtime,
                action=args.action, isolation=isolation)
        else:
            active = await service.activate(db, root, selected(args), args.approve_plan, runtime, choices=choices, scopes=args.scope, isolation=isolation)
        return {"state": "active_for_local_acceptance", **lifecycle.installed_response(active, db=db)}


def selected(args):
    fields = ("connector_id", "version", "release_id", "package_asset_id", "source_commit", "sha256")
    if any(getattr(args, key) is None for key in fields):
        raise ValueError("local_release_complete_identity_required")
    return service.ReleaseIdentity(**{key:getattr(args,key) for key in fields})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["verify", "stage", "plan", "activate", "renew", "recover", "revoke",
        "reconcile-revocation", "recover-revocation", "plan-restoration", "authorize-restoration"])
    parser.add_argument("--operation", choices=["activate", "renew", "recover"], default="activate", help="Operation reviewed by plan")
    parser.add_argument("--lease-seconds", type=int, default=authority.MAX_LIFETIME, help="Execution lease duration reviewed in plan (maximum 48 hours)")
    for key in ("connector-id", "version", "source-commit", "sha256", "authorization-id", "approve-plan"):
        parser.add_argument("--" + key)
    for key in ("release-id", "package-asset-id"):
        parser.add_argument("--" + key, type=int)
    parser.add_argument("--evidence-directory", type=Path)
    parser.add_argument("--mappings", type=Path)
    parser.add_argument("--isolation-report", type=Path, help="Fresh root-owned isolation inspection, bound into approval")
    parser.add_argument("--replacement-store", type=Path, help="Existing separate ordinary bundled store; restoration only")
    parser.add_argument("--corrupt-sha256", help="Reviewed SHA-256 of historical corrupt tombstone; recovery only")
    parser.add_argument("--clear-scopes", action="store_true", help="Explicit reviewed empty scope selection for bundled probe restoration")
    parser.add_argument("--scope", action="append")
    args = parser.parse_args()
    if args.action == "verify" and args.evidence_directory is None:
        parser.error("verify requires --evidence-directory (new retained result directory)")
    if args.action in {"revoke", "reconcile-revocation", "recover-revocation"} and args.authorization_id is None:
        parser.error("revocation requires --authorization-id")
    if args.action == "recover-revocation" and (args.corrupt_sha256 is None or not re.fullmatch(r"[a-f0-9]{64}", args.corrupt_sha256)):
        parser.error("recover-revocation requires --corrupt-sha256")
    if args.corrupt_sha256 is not None and args.action != "recover-revocation":
        parser.error("--corrupt-sha256 is restricted to recover-revocation")
    if args.clear_scopes and args.action not in {"plan-restoration", "authorize-restoration"}:
        parser.error("--clear-scopes is restricted to bundled restoration")
    try:
        print(json.dumps(asyncio.run(run(args)), default=str, sort_keys=True))
    except (OSError, ValueError, SQLAlchemyError, TypeError, KeyError, AttributeError) as error:
        code = str(error)
        if not re.fullmatch(r"[a-z_]{1,100}", code):
            code = "local_release_operation_failed"
        parser.exit(1, code + "\n")


if __name__ == "__main__":
    main()
