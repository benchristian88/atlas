"""Local operator-only staging/activation in an isolated qualification instance.

No network downloads, source credentials, catalogue edits or global qualification.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import time
from sqlalchemy.exc import SQLAlchemyError

from app.services import connector_lifecycle as lifecycle
from app.services.connector_catalogue import CataloguePackage, compatibility
from app.services.connector_contracts import strict_json, validate_manifest
from app.services.connector_qualification import (GRANT_FILE, OperatorQualificationVerifier,
    authorize, manifest_digest, require_test_store)
from app.services.connector_store import MAX_ARCHIVE_BYTES, _read_regular, _write
from app.services.connector_verification import verify_digest


def installation_authority():
    docker = os.getenv("ATLAS_INSTALL_METHOD") == "docker_compose" and os.geteuid() == os.getegid() == 10001
    if os.geteuid() != 0 and not docker:
        raise ValueError("qualification_requires_installation_authority")


def selected(args):
    root = require_test_store(lifecycle.package_store().root)
    if any(not re.fullmatch(r"[a-f0-9]{40}", item) for item in (args.atlas_commit, args.connector_commit)):
        raise ValueError("qualification_requires_exact_commits")
    if os.getenv("ATLAS_BUILD_ID") != args.atlas_commit:
        raise ValueError("qualification_atlas_build_mismatch")
    manifest = validate_manifest(strict_json(_read_regular(args.manifest, 256 * 1024)))
    if (manifest["id"] != args.connector_id or manifest["version"] != args.version
            or manifest["distribution"]["bundle_digest"] != args.digest
            or manifest["distribution"]["provenance"].get("source_commit") != args.connector_commit):
        raise ValueError("qualification_checkpoint_mismatch")
    verify_digest(_read_regular(args.bundle, MAX_ARCHIVE_BYTES), args.digest)
    package = CataloguePackage(args.connector_id, args.version, args.digest, manifest,
                               "operator-qualification", True, args.bundle)
    return root, package


def stage(args):
    root, package = selected(args)
    store = lifecycle.package_store()
    grant = {"schema_version": "1.0", "purpose": "operator-live-qualification", "store_path": str(root),
        "connector_id": package.connector_id, "version": package.version, "bundle_digest": package.bundle_digest,
        "manifest_digest": manifest_digest(package.manifest), "atlas_commit": args.atlas_commit,
        "connector_commit": args.connector_commit, "expires_at": int(time.time()) + 48 * 3600}
    created = False
    # Same protected install lock and no-replace publication as package staging.
    with store._lock():
        if (root / GRANT_FILE).exists():
            existing, _ = authorize(root, package.manifest)
            if existing["atlas_commit"] != args.atlas_commit:
                raise ValueError("qualification_checkpoint_mismatch")
        else:
            _write(root / GRANT_FILE, (json.dumps(grant, sort_keys=True) + "\n").encode())
            created = True
    try:
        stored = store.install(package, OperatorQualificationVerifier(root))
    except (OSError, ValueError):
        if created:
            with store._lock():
                (root / GRANT_FILE).unlink()
        raise
    print(json.dumps({"state": "staged_for_qualification", **stored.safe_metadata()}))


def apply_mappings(db, manifest, path):
    from sqlalchemy import select
    from app.models import ConnectorMapping
    from app.services import connector_mappings as mappings
    if path is None:
        return
    choices = strict_json(_read_regular(path, 16 * 1024), maximum=16 * 1024)
    declared = {(kind, row["key"]) for kind, row, _ in mappings.declarations(manifest)}
    if not isinstance(choices, list) or len(choices) > len(declared):
        raise ValueError("qualification_invalid_mappings")
    seen = set()
    for choice in choices:
        if not isinstance(choice, dict) or set(choice) != {"kind", "source_key", "target_key"}:
            raise ValueError("qualification_invalid_mappings")
        if any(not isinstance(value, str) for value in choice.values()):
            raise ValueError("qualification_invalid_mappings")
        identity = (choice["kind"], choice["source_key"])
        if identity not in declared or identity in seen or mappings.target(db, choice["kind"], choice["target_key"]) is None:
            raise ValueError("qualification_invalid_mappings")
        seen.add(identity)
        row = db.scalar(select(ConnectorMapping).where(ConnectorMapping.connector_id == manifest["id"],
            ConnectorMapping.connector_version == manifest["version"], ConnectorMapping.kind == choice["kind"],
            ConnectorMapping.source_key == choice["source_key"]))
        if row is None:
            row = ConnectorMapping(connector_id=manifest["id"], connector_version=manifest["version"],
                kind=choice["kind"], source_key=choice["source_key"])
            db.add(row)
        row.target_key, row.ignored = choice["target_key"], False
        row.asset_type_key = row.target_key if row.kind == "asset" else None
        row.relationship_type_key = row.target_key if row.kind == "relationship" else None
    db.flush()


def prepare(db, manifest, args):
    from sqlalchemy import or_, select
    from app.models import Integration
    from app.services.integration_connections import validate_scopes
    lifecycle.lock_connector(db, manifest["id"])
    if lifecycle.active_connector_runs(db, manifest["id"]):
        raise lifecycle.ConnectorInUse("qualification_wait_for_active_runs")
    rows = list(db.scalars(select(Integration).where(
        Integration.retired_at.is_(None), or_(Integration.plugin_id == manifest["id"],
            Integration.connector_id == manifest["id"])).with_for_update()))
    if any(row.connector_id is None or row.schedule_preset != "manual" for row in rows):
        raise ValueError("qualification_requires_generic_manual_connections")
    scopes = getattr(args, "scope", None)
    if scopes is not None:
        validate_scopes(manifest, scopes)
        for row in rows:
            row.selected_scopes = scopes
    apply_mappings(db, manifest, getattr(args, "mappings", None))
    return rows


def plan(args):
    from app.database import SessionLocal
    from app.services import connector_mappings as mappings
    from app.services.integration_connections import validate_dependents
    root, package = selected(args)
    authorize(root, package.manifest)
    with SessionLocal() as db:
        rows = prepare(db, package.manifest, args)
        state = mappings.mapping_state(db, package.manifest, auto_map=True)
        config_ready = True
        try:
            validate_dependents(db, package.manifest)
        except ValueError:
            config_ready = False
        print(json.dumps({"state": "qualification_plan", "mappings": state,
            "connections": len(rows), "dependent_configuration_ready": config_ready,
            "scopes": getattr(args, "scope", None)}))
        db.rollback()  # Preview never persists mappings, scopes or activation.


async def activate(args):
    from app.database import SessionLocal
    from app.audit import add_audit_event
    from app.services.integration_runtime import runtime
    root, package = selected(args)
    grant, _ = authorize(root, package.manifest)
    if grant["atlas_commit"] != args.atlas_commit:
        raise ValueError("qualification_checkpoint_mismatch")
    health = await runtime.health()
    if health.get("status") != "healthy" or compatibility(package.manifest, health)["state"] != "compatible":
        raise ValueError("qualification_runtime_incompatible")
    stored = lifecycle.package_store().install(package, OperatorQualificationVerifier(root))
    reference = {"connector_id": stored.connector_id, "version": stored.version, "digest": stored.bundle_digest[7:]}
    if (await runtime.verify_connector(reference))["state"] != "verified":
        raise ValueError("qualification_runtime_verification_failed")
    with SessionLocal() as db:
        prepare(db, package.manifest, args)
        active = lifecycle.activate(db, stored, health, operator_qualification=True)
        add_audit_event(db, action="connector.qualification_activated", target_type="connector_package",
            summary="Operator candidate activated in isolated qualification instance", metadata={**reference,
                "atlas_commit": args.atlas_commit, "connector_commit": args.connector_commit,
                "expires_at": grant["expires_at"], "scopes": getattr(args, "scope", None),
                "mapping_choices": bool(getattr(args, "mappings", None))})
        db.commit()
        print(json.dumps({"state": "active_for_qualification", **reference,
                          "source_qualification": "unqualified", "expires_at": grant["expires_at"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["stage", "plan", "activate", "revoke"])
    parser.add_argument("--ack-isolated-test-instance", action="store_true", required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--scope", action="append", help="Explicit selection for all dependent test connections")
    parser.add_argument("--mappings", type=Path, help="Reviewed local JSON kind/source_key/target_key choices")
    for key in ("connector-id", "version", "digest", "atlas-commit", "connector-commit"):
        parser.add_argument("--" + key)
    args = parser.parse_args()
    installation_authority()
    root = require_test_store(lifecycle.package_store().root)
    if args.action == "revoke":
        with lifecycle.package_store()._lock():
            (root / GRANT_FILE).unlink(missing_ok=True)
        print("Qualification permission revoked; retain history and settle any running jobs.")
        return
    if any(getattr(args, key) is None for key in ("manifest", "bundle", "connector_id", "version", "digest", "atlas_commit", "connector_commit")):
        parser.error("stage/activate require the complete exact checkpoint")
    if args.action == "stage":
        stage(args)
    elif args.action == "plan":
        plan(args)
    else:
        asyncio.run(activate(args))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, SQLAlchemyError) as error:
        # Codes only: no filesystem/source/credential/SQL details.
        code = str(error)
        if not re.fullmatch(r"[a-z_]{1,100}", code):
            code = "qualification_operation_failed"
        raise SystemExit(code) from None
