"""Global package management and safe scoped configured Integration views."""
from __future__ import annotations

from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, RequestContext, require_global, require_permission, scope_condition
from app.database import get_db
from app.models import Customer, InstalledConnectorPackage, Integration, Site
from app.services import connector_lifecycle as lifecycle
from app.services.integration_runtime import runtime
from app.services.integration_connections import UpdateRequiresConfiguration

router = APIRouter(tags=["integrations"])
_CONNECTOR_ID = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*")


class PackageSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    version: str = Field(min_length=1, max_length=64)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")


def _id(connector_id: str):
    if len(connector_id) > 100 or not _CONNECTOR_ID.fullmatch(connector_id):
        raise HTTPException(404, "Connector not found")


def _installed(db):
    return {item.connector_id: item for item in db.scalars(
        select(InstalledConnectorPackage).order_by(InstalledConnectorPackage.connector_id))}


@router.get("/integrations")
def configured_integrations(context: RequestContext,
        principal: Principal = Depends(require_permission("integrations.view")), db: Session = Depends(get_db)):
    statement = select(Integration, Customer.name, Site.name).join(Customer, Customer.id == Integration.customer_id).join(Site, Site.id == Integration.site_id).where(scope_condition(principal, "integrations.view", Integration.customer_id, Integration.site_id))
    if context.customer_id:
        statement = statement.where(Integration.customer_id == context.customer_id)
    if context.site_id:
        statement = statement.where(Integration.site_id == context.site_id)
    # Preserve useful legacy identity/status without exposing endpoint, username
    # or secret references; no configuration/edit flow is added here.
    from app.services.integration_connections import response
    from app.services.integration_secrets import AtlasEncryptedSecretProvider
    provider = AtlasEncryptedSecretProvider(db)
    result = []
    for item, customer_name, site_name in db.execute(statement.order_by(Integration.name, Integration.id).limit(500)):
        if item.connector_id:
            value = response(item, provider, detail=False)
        else:
            value = {"id": item.id, "name": item.name, "connector_id": item.plugin_id,
                "customer_id": item.customer_id, "site_id": item.site_id, "status": item.status, "generic": False}
        result.append({**value, "customer_name": customer_name, "site_name": site_name})
    return result



@router.get("/integration-runtime")
async def runtime_health(principal: Principal = Depends(require_permission("integration_runtime.view")), db: Session = Depends(get_db)):
    require_global(principal, "integration_runtime.view")
    return {**await runtime.health(), "installed_connector_count": len(_installed(db))}


def catalogue_entries(db, principal, health):
    from app.services.connector_catalogue import catalogue
    entries = catalogue.entries(runtime=health, installed=_installed(db))
    if principal.can("integration_runtime.manage"):
        from app.services.integration_connections import validate_dependents
        from app.services.connector_mappings import require_resolved
        for entry in entries:
            if entry["state"] != "update_available":
                continue
            manifest = catalogue.get(entry["connector_id"], entry["version"]).manifest
            try:
                require_resolved(db, manifest)
                validate_dependents(db, manifest, lock=False)
            except ValueError:
                entry.update(state="update_requires_configuration", supported_actions=[],
                    message="Review dependent connection configuration and required global mappings before updating.")
    return entries


@router.get("/integration-catalogue")
async def catalogue_list(principal: Principal = Depends(require_permission("integrations.view")), db: Session = Depends(get_db)):
    from app.services.connector_catalogue import catalogue
    from app.services.connector_contracts import ConnectorPackageError
    try:
        return {"entries": catalogue_entries(db, principal, await runtime.health()),
                "source": "bootstrap", "checked_at": datetime.now(timezone.utc).isoformat(), "verification_status": "metadata_verified"}
    except ConnectorPackageError:
        raise HTTPException(503, "The packaged Connector catalogue could not be verified") from None


@router.get("/integration-catalogue/{connector_id}")
async def catalogue_detail(connector_id: str, principal: Principal = Depends(require_permission("integrations.view")), db: Session = Depends(get_db)):
    from app.services.connector_catalogue import catalogue
    from app.services.connector_contracts import ConnectorPackageError
    _id(connector_id)
    try:
        entry = next((item for item in catalogue_entries(db, principal, await runtime.health())
                      if item["connector_id"] == connector_id), None)
    except ConnectorPackageError:
        raise HTTPException(503, "The packaged Connector catalogue could not be verified") from None
    if entry is None:
        raise HTTPException(404, "Connector not found")
    return entry


@router.get("/installed-connectors")
def installed_list(principal: Principal = Depends(require_permission("integration_runtime.view")), db: Session = Depends(get_db)):
    require_global(principal, "integration_runtime.view")
    return [lifecycle.installed_response(item) for item in _installed(db).values()]


@router.get("/installed-connectors/{connector_id}")
def installed_detail(connector_id: str, principal: Principal = Depends(require_permission("integration_runtime.view")), db: Session = Depends(get_db)):
    require_global(principal, "integration_runtime.view")
    _id(connector_id)
    active = db.get(InstalledConnectorPackage, connector_id)
    if active is None:
        raise HTTPException(404, "Installed Connector not found")
    return lifecycle.installed_response(active)


async def _install(connector_id: str, payload: PackageSelection, request: Request, principal: Principal, db: Session):
    from app.services.connector_catalogue import catalogue, compatibility
    from app.services.connector_verification import ConnectorPackageError
    require_global(principal, "integration_runtime.manage")
    _id(connector_id)
    try:
        package = catalogue.get(connector_id, payload.version)
        if not package.package_available or package.bundle_digest != "sha256:" + payload.digest:
            raise HTTPException(409, "A verified release bundle is not available for this selection")
        health = await runtime.health()
        if health["status"] != "healthy":
            raise HTTPException(409, "The approved runtime must be healthy before package activation")
        result = compatibility(package.manifest, health)
        if result["state"] not in {"compatible", "installable"}:
            raise HTTPException(409, "This Connector requires a compatible Atlas runtime")
        lifecycle.lock_connector(db, connector_id)
        # Activation validates all live generic owners against the new Manifest.
        # Legacy owners retain the conservative I1 update guard.
        if db.scalar(select(Integration.id).where(Integration.connector_id.is_(None), Integration.plugin_id == connector_id).limit(1)):
            raise lifecycle.ConnectorInUse("Legacy configured connections must be migrated before changing this Connector package")
        stored = lifecycle.package_store().install(package, catalogue.verifier())
        reference = {"connector_id": stored.connector_id, "version": stored.version, "digest": stored.bundle_digest.removeprefix("sha256:")}
        if (await runtime.verify_connector(reference))["state"] != "verified":
            raise HTTPException(409, "The runtime could not verify this installed package")
        active = lifecycle.activate(db, stored, health)
        add_audit_event(db, action="connector.activated", target_type="connector_package", actor=principal.user,
            summary="Verified Connector package activated", metadata=reference, request=request)
        db.commit()
        return lifecycle.installed_response(active)
    except UpdateRequiresConfiguration:
        db.rollback()
        raise HTTPException(409, {"code": "update_requires_configuration", "message": "Review dependent connection configuration before updating. The active version is unchanged."}) from None
    except lifecycle.ConnectorInUse as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from None
    except ConnectorPackageError as exc:
        db.rollback()
        raise HTTPException(409, {"code": exc.code, "message": "Connector package verification or installation was unsuccessful"}) from None
    except (OSError, ValueError, SQLAlchemyError):
        db.rollback()
        raise HTTPException(409, "Connector package activation was unsuccessful") from None
    except HTTPException:
        db.rollback()
        raise


@router.post("/integration-catalogue/{connector_id}/install")
async def install_connector(connector_id: str, payload: PackageSelection, request: Request,
        principal: Principal = Depends(require_permission("integration_runtime.manage")), db: Session = Depends(get_db)):
    return await _install(connector_id, payload, request, principal, db)


@router.post("/integration-catalogue/{connector_id}/activate")
async def activate_connector(connector_id: str, payload: PackageSelection, request: Request,
        principal: Principal = Depends(require_permission("integration_runtime.manage")), db: Session = Depends(get_db)):
    # Update and rollback deliberately select the same verified immutable tuple.
    return await _install(connector_id, payload, request, principal, db)


@router.delete("/installed-connectors/{connector_id}")
def uninstall_connector(connector_id: str, request: Request,
        principal: Principal = Depends(require_permission("integration_runtime.manage")), db: Session = Depends(get_db)):
    require_global(principal, "integration_runtime.manage")
    _id(connector_id)
    lifecycle.lock_connector(db, connector_id)
    active = db.get(InstalledConnectorPackage, connector_id)
    if active is None:
        raise HTTPException(404, "Installed Connector not found")
    try:
        lifecycle.require_unused(db, connector_id)
        reference = {"connector_id": active.connector_id, "version": active.version, "digest": active.bundle_digest}
        store = lifecycle.package_store()
        quarantine = store.quarantine_connector(connector_id)
        db.delete(active)
        add_audit_event(db, action="connector.uninstalled", target_type="connector_package", actor=principal.user,
            summary="Connector package deactivated; knowledge history retained", metadata=reference, request=request)
        db.commit()
        try:
            store.finish_remove(quarantine)
        except (OSError, ValueError):
            # Active authority is already removed. The quarantined directory
            # has no executable identity; report cleanup without restoring it.
            return {"status": "removed", "cleanup_pending": True, **reference}
        return {"status": "removed", "cleanup_pending": False, **reference}
    except UpdateRequiresConfiguration:
        db.rollback()
        raise HTTPException(409, {"code": "update_requires_configuration", "message": "Review dependent connection configuration before updating. The active version is unchanged."}) from None
    except lifecycle.ConnectorInUse as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from None
    except (OSError, ValueError, SQLAlchemyError):
        db.rollback()
        if "quarantine" in locals():
            try:
                store.restore(quarantine)
            except (OSError, ValueError):
                raise HTTPException(409, "Package removal could not be completed; administrator repair is required") from None
        raise HTTPException(409, "Connector package removal was unsuccessful") from None
