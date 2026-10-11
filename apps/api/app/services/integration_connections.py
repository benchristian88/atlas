"""Generic scoped connection policy over exact verified installed packages."""
import uuid

from sqlalchemy import select

from atlas_connector_sdk.configuration import validate_configuration
from app.models import InstalledConnectorPackage, Integration
from app.services import connector_lifecycle as lifecycle
from app.services.connector_contracts import strict_json, validate_manifest
from app.services.connector_store import _read_regular
from app.services.connector_mappings import require_resolved
from app.services.integration_secrets import AtlasEncryptedSecretProvider


def installed_manifest(db, connector_id):
    record = db.get(InstalledConnectorPackage, connector_id)
    if record is None or record.status != "active" or record.verification_status != "verified":
        raise ValueError("A verified active Connector is required")
    store = lifecycle.package_store()
    store.verify_connector(record.connector_id, record.version, "sha256:" + record.bundle_digest)
    directory = store.root / record.connector_id / record.version / record.bundle_digest
    manifest = validate_manifest(strict_json(_read_regular(directory / "manifest.json", 256 * 1024)), activation=True)
    require_resolved(db, manifest)
    return record, manifest


def validate_scopes(manifest, selection):
    declared = {row["key"]: row for row in manifest.get("discovery_scopes", [])}
    if len(set(selection)) != len(selection) or not set(selection) <= declared.keys():
        raise ValueError("Select only declared Connector scopes")
    if any(row["required"] and key not in selection for key, row in declared.items()):
        raise ValueError("Required Connector scopes must remain selected")


class UpdateRequiresConfiguration(ValueError):
    pass


def validate_dependents(db, manifest, *, lock=True):
    provider = AtlasEncryptedSecretProvider(db)
    query = select(Integration).where(Integration.connector_id == manifest["id"], Integration.retired_at.is_(None))
    rows = list(db.scalars(query.with_for_update() if lock else query))
    for row in rows:
        try:
            validate_configuration(manifest, row.config_json, configured_fields=provider.state(row))
            validate_scopes(manifest, row.selected_scopes)
        except ValueError:
            raise UpdateRequiresConfiguration("Update requires configuration: review dependent connections before activation") from None
    return rows


def response(integration, provider, *, detail=True):
    fields = provider.state(integration) if integration.connector_id else []
    value = {"id": integration.id, "name": integration.name,
        "connector_id": integration.connector_id or integration.plugin_id,
        "customer_id": integration.customer_id, "site_id": integration.site_id,
        "status": "retired" if integration.retired_at else "disabled" if not integration.enabled else "configured" if fields else "unconfigured",
        "generic": integration.connector_id is not None, "enabled": integration.enabled,
        "credential_configured": bool(fields), "configured_fields": fields,
        "retired_at": integration.retired_at, "last_test_at": integration.last_test_at,
        "last_test_status": integration.last_test_status, "source_version": integration.source_version,
        "source_compatibility": integration.source_compatibility}
    if detail:
        value.update(connector_version=integration.connector_version, connector_digest=integration.connector_digest,
            data_source_id=integration.data_source_id, config_schema_version=integration.config_schema_version,
            config=integration.config_json, selected_scopes=integration.selected_scopes)
    return value
