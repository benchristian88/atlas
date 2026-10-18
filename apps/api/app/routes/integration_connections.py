"""Scoped write-only Integration CRUD, bounded probes and global mapping admin."""
from datetime import datetime, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from atlas_connector_sdk.contracts import ContractError
from atlas_connector_sdk.configuration import validate_configuration, source_compatibility, visible
from app.audit import add_audit_event
from app.authorization import Principal, require_permission, require_scope, require_global, scope_condition
from app.database import get_db
from app.models import Integration, DataSource, Site, InstalledConnectorPackage, ConnectorMapping
from app.services import connector_lifecycle as lifecycle
from app.services import connector_mappings as mappings
from app.services.integration_connections import installed_manifest, response, validate_scopes, protect_source_identity, SourceIdentityLocked
from app.services.integration_secrets import AtlasEncryptedSecretProvider, JobSecretLease, SecretProviderError
from app.services.integration_runtime import runtime

router = APIRouter(tags=["integrations"])


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class ConnectionCreate(Input):
    creation_key: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    customer_id: uuid.UUID
    site_id: uuid.UUID
    connector_id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", max_length=100)
    config: dict = Field(max_length=32)
    credentials: dict[str, SecretStr] = Field(repr=False, max_length=32)
    selected_scopes: list[str] = Field(default_factory=list, max_length=16)
    enabled: bool = True


class ConnectionUpdate(Input):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: dict | None = Field(default=None, max_length=32)
    selected_scopes: list[str] | None = Field(default=None, max_length=16)
    enabled: bool | None = None


class Credentials(Input):
    values: dict[str, SecretStr] = Field(repr=False, max_length=32)


class Confirm(Input):
    confirmed: bool


class MappingInput(Input):
    version: str = Field(max_length=64)
    kind: str = Field(pattern=r"^(asset|relationship)$")
    source_key: str = Field(max_length=100)
    target_key: str | None = Field(default=None, max_length=100)
    ignored: bool = False


def scoped(db, principal, permission, identifier, *, lock=False):
    query = select(Integration).where(Integration.id == identifier,
        scope_condition(principal, permission, Integration.customer_id, Integration.site_id))
    if lock:
        visible_row = db.scalar(query)
        if visible_row is not None and visible_row.connector_id:
            lifecycle.lock_connector(db, visible_row.connector_id)
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Integration not found")
    return row


def require_live(row):
    if row.retired_at or row.connector_id is None:
        raise HTTPException(409, "This connection cannot be changed through the generic Integration workflow")


def validate_scope(db, principal, permission, customer_id, site_id):
    require_scope(principal, permission, customer_id, site_id, hide_existence=True)
    site = db.get(Site, site_id)
    if site is None or site.customer_id != customer_id:
        raise HTTPException(404, "Customer/site not found")


def audit(db, row, principal, request, action, *, metadata=None, success=True):
    add_audit_event(db, action="integration." + action, target_type="integration", target_id=row.id,
        customer_id=row.customer_id, site_id=row.site_id, actor=principal.user, request=request,
        summary="Integration " + action.replace("_", " "), metadata=metadata, success=success)


def invalid(db, error):
    db.rollback()
    code = error.code if isinstance(error, ContractError) else "integration_configuration_unavailable"
    raise HTTPException(409, {"code": code, "message": "Check the declared configuration, credential state, Connector mappings and verified package."}) from None


async def ready(db, connector_id):
    record, manifest = installed_manifest(db, connector_id)
    from app.services.connector_catalogue import compatibility
    if compatibility(manifest, await runtime.health())["state"] != "compatible":
        raise HTTPException(409, "A compatible healthy runtime is required for this operation")
    return record, manifest


def form(record, manifest):
    return {"connector_id": record.connector_id, "version": record.version, "digest": record.bundle_digest,
        "name": manifest["display"]["name"], "manifest_version": manifest["manifest_version"],
        "connection_fields": manifest["connection_fields"], "discovery_scopes": manifest.get("discovery_scopes", []),
        "capabilities": manifest["capabilities"], "source_versions": manifest["source_versions"]}


@router.get("/integration-forms")
def connection_forms(principal: Principal = Depends(require_permission("integrations.view")), db: Session = Depends(get_db)):
    result = []
    for row in db.scalars(select(InstalledConnectorPackage).order_by(InstalledConnectorPackage.connector_id)):
        try:
            record, manifest = installed_manifest(db, row.connector_id)
            result.append(form(record, manifest))
        except (ValueError, OSError):
            continue  # No actionable form for an unavailable/unresolved package.
    return result


@router.get("/integrations/{integration_id}")
def integration_detail(integration_id: uuid.UUID, principal: Principal = Depends(require_permission("integrations.view")), db: Session = Depends(get_db)):
    row = scoped(db, principal, "integrations.view", integration_id)
    value = response(row, AtlasEncryptedSecretProvider(db))
    if principal.can("integration_runtime.manage", None, None):
        value["debug_next_run"] = bool(row.debug_next_run)
    site = db.get(Site, row.site_id)
    value["site_name"] = site.name
    from app.services.discovery_orchestration import active_run
    current = active_run(db, row.id)
    value.update(current_run_id=current.id if current else None, current_run_status=current.status if current else None)
    value.update(discovery_capable=False, scheduling_capable=False, discovery_configured=False)
    try:
        record, manifest = installed_manifest(db, row.connector_id) if row.connector_id else (None, None)
        if manifest and (record.version, record.bundle_digest) == (row.connector_version, row.connector_digest):
            value.update(discovery_capable=manifest["capabilities"]["discover"] == "read_only",
                scheduling_capable=manifest["capabilities"]["scheduling"])
            validate_configuration(manifest, row.config_json, configured_fields=AtlasEncryptedSecretProvider(db).state(row))
            validate_scopes(manifest, row.selected_scopes)
            value["discovery_configured"] = True
    except (ValueError, OSError):
        pass
    return value


@router.post("/integrations", status_code=201)
async def create_integration(payload: ConnectionCreate, request: Request,
        principal: Principal = Depends(require_permission("integrations.manage")), db: Session = Depends(get_db)):
    validate_scope(db, principal, "integrations.manage", payload.customer_id, payload.site_id)
    # Serialize retries as well as global package changes; ownership and the
    # database unique constraint prevent duplicate provenance sources.
    lifecycle.lock_connector(db, payload.connector_id)
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"integration-create:{payload.customer_id}:{payload.site_id}:{payload.creation_key}"})
    existing = db.scalar(select(Integration).where(Integration.customer_id == payload.customer_id,
        Integration.site_id == payload.site_id, Integration.creation_key == payload.creation_key))
    if existing:
        if existing.connector_id != payload.connector_id:
            raise HTTPException(409, "Creation request already used")
        return response(existing, AtlasEncryptedSecretProvider(db))
    try:
        record, manifest = await ready(db, payload.connector_id)
        values = {key: value.get_secret_value() for key, value in payload.credentials.items()}
        config = validate_configuration(manifest, payload.config, values)
        validate_scopes(manifest, payload.selected_scopes)
        source = DataSource(customer_id=payload.customer_id, site_id=payload.site_id, name=payload.name,
            source_type="connector", status="active", trust_level="observed")
        db.add(source)
        db.flush()
        row = Integration(id=uuid.uuid4(), customer_id=payload.customer_id, site_id=payload.site_id,
            creation_key=payload.creation_key, name=payload.name, plugin_id=record.connector_id,
            base_url="", username_or_token_id="", secret_reference="", status="configured",
            connector_id=record.connector_id, connector_version=record.version, connector_digest=record.bundle_digest,
            data_source_id=source.id, config_schema_version=manifest["manifest_version"], config_json=config,
            selected_scopes=payload.selected_scopes, enabled=payload.enabled)
        db.add(row)
        db.flush()
        provider = AtlasEncryptedSecretProvider(db)
        if values:
            provider.create(row, values)
        values.clear()
        from app.services import discovery_orchestration as discovery
        initial = None
        can_run = db.scalar(select(Integration.id).where(Integration.id == row.id,
            scope_condition(principal, "integrations.run", Integration.customer_id, Integration.site_id))) is not None
        if manifest["capabilities"]["discover"] == "read_only" and row.enabled and can_run:
            if manifest["capabilities"]["scheduling"]:
                row.schedule_preset = "hourly"
                row.next_run_at = discovery.next_run("hourly", datetime.now(timezone.utc))
            try:
                initial = await discovery.create_run(db, row, trigger="onboarding", user_id=principal.user.id)
            except (ValueError, OSError, RuntimeError):
                row.last_error_code = "initial_discovery_unavailable"
        audit(db, row, principal, request, "created")
        audit(db, row, principal, request, "credential_configured", metadata={"fields": provider.state(row)})
        result = response(row, provider)
        db.commit()
        if initial:
            discovery.enqueue(initial.id)
        return result
    except HTTPException:
        db.rollback()
        raise
    except (ValueError, OSError, RuntimeError, SQLAlchemyError) as error:
        invalid(db, error)


@router.patch("/integrations/{integration_id}")
def update_integration(integration_id: uuid.UUID, payload: ConnectionUpdate, request: Request,
        principal: Principal = Depends(require_permission("integrations.manage")), db: Session = Depends(get_db)):
    row = scoped(db, principal, "integrations.manage", integration_id, lock=True)
    require_live(row)
    lifecycle.lock_connector(db, row.connector_id)
    try:
        record, manifest = installed_manifest(db, row.connector_id)
        provider = AtlasEncryptedSecretProvider(db)
        if payload.config is not None:
            protect_source_identity(db, row, manifest, payload.config)
        if payload.config is not None or payload.selected_scopes is not None or payload.enabled is False:
            from app.services.discovery_orchestration import cancel_integration_runs
            cancel_integration_runs(db, row.id)
        if payload.config is not None:
            # Clearing credentials remains a legitimate unconfigured state.
            names = provider.state(row) or [field["key"] for field in manifest["connection_fields"] if field["secret"]]
            row.config_json = validate_configuration(manifest, payload.config, configured_fields=names)
        if payload.selected_scopes is not None:
            validate_scopes(manifest, payload.selected_scopes)
            row.selected_scopes = payload.selected_scopes
        if payload.name is not None:
            row.name = payload.name
        if payload.enabled is not None and payload.enabled != row.enabled:
            row.enabled = payload.enabled
            from app.services.discovery_orchestration import next_run
            row.next_run_at = next_run(row.schedule_preset, datetime.now(timezone.utc)) if row.enabled else None
            audit(db, row, principal, request, "enabled" if row.enabled else "disabled")
        if payload.config is not None or payload.selected_scopes is not None:
            row.last_test_at = row.last_test_status = row.source_version = row.source_compatibility = None
            row.last_error_code = None
        audit(db, row, principal, request, "configuration_changed")
        result = response(row, provider)
        db.commit()
        return result
    except SourceIdentityLocked as error:
        db.rollback()
        raise HTTPException(409, {"code": "source_identity_locked", "message": str(error)}) from None
    except (ValueError, OSError, SQLAlchemyError) as error:
        invalid(db, error)


@router.put("/integrations/{integration_id}/credentials")
def replace_credentials(integration_id: uuid.UUID, payload: Credentials, request: Request,
        principal: Principal = Depends(require_permission("integrations.manage")), db: Session = Depends(get_db)):
    row = scoped(db, principal, "integrations.manage", integration_id, lock=True)
    require_live(row)
    try:
        _, manifest = installed_manifest(db, row.connector_id)
        values = {key: value.get_secret_value() for key, value in payload.values.items()}
        validate_configuration(manifest, row.config_json, values)
        provider = AtlasEncryptedSecretProvider(db)
        from app.services.discovery_orchestration import cancel_integration_runs
        cancel_integration_runs(db, row.id)
        action = "credential_replaced" if provider.state(row) else "credential_configured"
        provider.replace(row, values)
        values.clear()
        row.last_test_at = row.last_test_status = row.source_version = row.source_compatibility = None
        row.last_error_code = None
        audit(db, row, principal, request, action, metadata={"fields": provider.state(row)})
        result = response(row, provider)
        db.commit()
        return result
    except (ValueError, OSError, RuntimeError, SQLAlchemyError) as error:
        invalid(db, error)


@router.delete("/integrations/{integration_id}/credentials")
def clear_credentials(integration_id: uuid.UUID, payload: Confirm, request: Request,
        principal: Principal = Depends(require_permission("integrations.manage")), db: Session = Depends(get_db)):
    row = scoped(db, principal, "integrations.manage", integration_id, lock=True)
    require_live(row)
    if not payload.confirmed:
        raise HTTPException(422, "Explicit credential removal confirmation is required")
    provider = AtlasEncryptedSecretProvider(db)
    from app.services.discovery_orchestration import cancel_integration_runs
    cancel_integration_runs(db, row.id)
    provider.delete(row)
    row.last_test_at = row.last_test_status = row.source_version = row.source_compatibility = None
    row.last_error_code = None
    audit(db, row, principal, request, "credential_cleared")
    result = response(row, provider)
    db.commit()
    return result


@router.delete("/integrations/{integration_id}")
def retire_integration(integration_id: uuid.UUID, payload: Confirm, request: Request,
        principal: Principal = Depends(require_permission("integrations.manage")), db: Session = Depends(get_db)):
    row = scoped(db, principal, "integrations.manage", integration_id, lock=True)
    if not row.connector_id or not payload.confirmed:
        raise HTTPException(409, "Confirm removal of a generic connection")
    lifecycle.lock_connector(db, row.connector_id)
    provider = AtlasEncryptedSecretProvider(db)
    from app.services.discovery_orchestration import cancel_integration_runs
    cancel_integration_runs(db, row.id)
    provider.delete(row)
    row.enabled = False
    row.next_run_at = None
    row.retired_at = row.retired_at or datetime.now(timezone.utc)
    audit(db, row, principal, request, "retired")
    result = response(row, provider)
    db.commit()
    return result


async def invoke(record, manifest, config, values, request_id):
    result = await runtime.test_connection({"connector_id": record.connector_id, "version": record.version, "digest": record.bundle_digest}, config, values, request_id)
    result["compatibility"] = source_compatibility(manifest, result.get("source_version"))
    if result["compatibility"] == "known_incompatible":
        result.update(success=False, category="source_incompatible")
    return result


@router.post("/integration-forms/{connector_id}/test-connection")
async def preview_connection(connector_id: str, payload: ConnectionCreate, request: Request,
        principal: Principal = Depends(require_permission("integrations.run")), db: Session = Depends(get_db)):
    validate_scope(db, principal, "integrations.run", payload.customer_id, payload.site_id)
    validate_scope(db, principal, "integrations.manage", payload.customer_id, payload.site_id)
    if connector_id != payload.connector_id:
        raise HTTPException(422, "Connector identity does not match")
    try:
        record, manifest = await ready(db, connector_id)
        values = {key: value.get_secret_value() for key, value in payload.credentials.items()}
        config = validate_configuration(manifest, payload.config, values)
        add_audit_event(db, action="integration.preview_test_requested", target_type="connector_package", actor=principal.user,
            customer_id=payload.customer_id, site_id=payload.site_id, request=request,
            summary="Unsaved Integration connection test requested", metadata={"connector_id": record.connector_id, "version": record.version})
        lease = JobSecretLease(uuid.uuid4(), datetime.now(timezone.utc) + timedelta(seconds=30), values)
        try:
            result = await invoke(record, manifest, config, lease.values, lease.request_id)
            add_audit_event(db, action="integration.preview_test_result", target_type="connector_package", actor=principal.user,
                customer_id=payload.customer_id, site_id=payload.site_id, request=request, success=result["success"],
                summary="Unsaved Integration connection test result", metadata={"category": result["category"]})
            db.commit()
            return result
        finally:
            lease.revoke()
    except (ValueError, OSError, RuntimeError) as error:
        invalid(db, error)


@router.post("/integrations/{integration_id}/test-connection")
async def test_connection(integration_id: uuid.UUID, request: Request,
        principal: Principal = Depends(require_permission("integrations.run")), db: Session = Depends(get_db)):
    row = scoped(db, principal, "integrations.run", integration_id, lock=True)
    require_live(row)
    lifecycle.lock_connector(db, row.connector_id)
    try:
        record, manifest = installed_manifest(db, row.connector_id)
        if (record.version, record.bundle_digest) != (row.connector_version, row.connector_digest):
            raise HTTPException(409, "Connection configuration requires the active Connector identity")
        provider = AtlasEncryptedSecretProvider(db)
        validate_configuration(manifest, row.config_json, configured_fields=provider.state(row))
        required = [field["key"] for field in manifest["connection_fields"] if field["secret"] and field["required"] and visible(field, row.config_json)]
        audit(db, row, principal, request, "test_requested")
        from app.services.connector_catalogue import compatibility
        if compatibility(manifest, await runtime.health())["state"] != "compatible":
            result = {"success": False, "category": "runtime_unavailable", "source_version": None, "compatibility": "unknown"}
        else:
            with provider.materialize_for_job(row, uuid.uuid4(), required) as lease:
                result = await invoke(record, manifest, row.config_json, lease.values, lease.request_id)
        row.last_test_at = datetime.now(timezone.utc)
        row.last_test_status = result["category"]
        if result["success"]:
            row.last_error_code = None
        row.source_version = result.get("source_version")
        row.source_compatibility = result["compatibility"]
        audit(db, row, principal, request, "test_result", metadata={"category": result["category"]}, success=result["success"])
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except (ValueError, OSError, RuntimeError, SQLAlchemyError) as error:
        invalid(db, error)


@router.get("/connector-mappings/{connector_id}")
def mapping_list(connector_id: str, version: str | None = None,
        principal: Principal = Depends(require_permission("integration_runtime.view")), db: Session = Depends(get_db)):
    require_global(principal, "integration_runtime.view")
    from app.services.connector_catalogue import catalogue
    try:
        manifest = catalogue.get(connector_id, version).manifest
        return {"connector_id": connector_id, "version": manifest["version"], "mappings": mappings.mapping_state(db, manifest)}
    except (ValueError, OSError):
        raise HTTPException(404, "Connector version not found") from None


@router.put("/connector-mappings/{connector_id}")
def resolve_mapping(connector_id: str, payload: MappingInput, request: Request,
        principal: Principal = Depends(require_permission("integration_runtime.manage")), db: Session = Depends(get_db)):
    require_global(principal, "integration_runtime.manage")
    from app.services.connector_catalogue import catalogue
    lifecycle.lock_connector(db, connector_id)
    if lifecycle.active_connector_runs(db, connector_id):
        raise HTTPException(409, "Wait for active discovery runs to settle before changing mappings")
    try:
        manifest = catalogue.get(connector_id, payload.version).manifest
        declared = next((row for kind, row, _ in mappings.declarations(manifest) if kind == payload.kind and row["key"] == payload.source_key), None)
        if declared is None or payload.ignored and (declared["required"] or payload.target_key is not None):
            raise ValueError
        if not payload.ignored and mappings.target(db, payload.kind, payload.target_key) is None:
            raise ValueError
        row = db.scalar(select(ConnectorMapping).where(ConnectorMapping.connector_id == connector_id,
            ConnectorMapping.connector_version == payload.version, ConnectorMapping.kind == payload.kind,
            ConnectorMapping.source_key == payload.source_key))
        if row is None:
            row = ConnectorMapping(connector_id=connector_id, connector_version=payload.version, kind=payload.kind, source_key=payload.source_key)
            db.add(row)
        row.target_key, row.ignored = payload.target_key, payload.ignored
        row.asset_type_key = payload.target_key if payload.kind == "asset" else None
        row.relationship_type_key = payload.target_key if payload.kind == "relationship" else None
        db.flush()
        state = mappings.mapping_state(db, manifest)
        selected = next(item for item in state if item["kind"] == payload.kind and item["source_key"] == payload.source_key)
        if not selected["resolved"]:
            raise ValueError
        add_audit_event(db, action="connector.mapping_changed", target_type="connector_package", actor=principal.user,
            summary="Global Connector taxonomy mapping changed", request=request,
            metadata={"connector_id": connector_id, "version": payload.version, "kind": payload.kind, "source_key": payload.source_key, "target_key": payload.target_key, "ignored": payload.ignored})
        db.commit()
        return {"connector_id": connector_id, "version": payload.version, "mappings": state}
    except (ValueError, OSError, SQLAlchemyError) as error:
        invalid(db, error)
