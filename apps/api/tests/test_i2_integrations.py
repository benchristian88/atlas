"""Transactional PostgreSQL I2 ownership, write-only credentials and probe tests."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json
import os
import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import create_engine, select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import pytest

from app.models import (Asset, AssetType, AuditEvent, Customer, DataSource, DiscoveryRun, EvidenceRecord,
    Integration, IntegrationSecret, Site, Workspace)
from app.routes import integration_connections as routes
from app.services import connector_lifecycle as lifecycle
from app.services.connector_catalogue import catalogue
from app.services.connector_store import PackageStore
from app.services.integration_secrets import AtlasEncryptedSecretProvider, SecretProviderError, decrypt_fields
from app.services.encrypted_data import rewrap_integrations
from app.services.backup_archive import BackupError
from tests.test_administration import make_principal, request
from tests.test_connector_packages import runtime as healthy_runtime

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def db():
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            yield db
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def setup(db, tmp_path, monkeypatch):
    principal = make_principal("integrations.view", "integrations.manage", "integrations.run", "integration_runtime.manage", "integration_runtime.view")
    principal.user.email = uuid.uuid4().hex + "@example.test"
    db.add(principal.user)
    workspace = Workspace(name="I2 fixture", slug=uuid.uuid4().hex)
    db.add(workspace)
    db.flush()
    customer = Customer(name="I2 scope", workspace_id=workspace.id)
    db.add(customer)
    db.flush()
    site = Site(name="I2 site", customer_id=customer.id)
    db.add(site)
    db.flush()
    store = PackageStore(tmp_path / "store")
    monkeypatch.setattr(lifecycle, "package_store", lambda: store)
    package = catalogue.get("proxmox", "0.1.0")
    stored = store.install(package, catalogue.verifier())
    health = healthy_runtime(baseline_id="atlas-ansible-i1-v1", baseline_digest="b" * 64)
    lifecycle.activate(db, stored, health)
    async def healthy(): return health
    monkeypatch.setattr(routes.runtime, "health", healthy)
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", secrets.token_hex(32))
    payload = routes.ConnectionCreate(creation_key=uuid.uuid4(), name="Probe fixture", customer_id=customer.id, site_id=site.id,
        connector_id="proxmox", config={"endpoint": "https://192.168.10.2:8006"},
        credentials={"token_id": "fixture_" + secrets.token_hex(8) + "@pve!probe", "token_secret": secrets.token_urlsafe(32)})
    db.commit()
    return principal, payload, stored


def create(db, setup):
    principal, payload, _ = setup
    return asyncio.run(routes.create_integration(payload, request(), principal, db))


def test_scoped_creation_is_atomic_retry_safe_and_write_only(db, setup):
    result = create(db, setup)
    principal, payload, _ = setup
    row = db.get(Integration, result["id"])
    assert row.data_source_id == result["data_source_id"]
    source = db.get(DataSource, row.data_source_id)
    assert (source.customer_id, source.site_id) == (row.customer_id, row.site_id)
    before = db.scalar(select(func.count()).select_from(DataSource))
    assert create(db, setup)["id"] == row.id
    assert db.scalar(select(func.count()).select_from(DataSource)) == before
    assert result["credential_configured"]
    assert {"credential_reference", "secret_reference", "encrypted_fields"}.isdisjoint(result)
    values = [value.get_secret_value() for value in payload.credentials.values()]
    stored = db.get(IntegrationSecret, row.credential_reference)
    assert all(value not in json.dumps(stored.encrypted_fields) for value in values)
    assert all(value not in json.dumps(row.config_json) for value in values)
    detail = routes.integration_detail(row.id, principal, db)
    assert all(value not in json.dumps(detail, default=str) for value in values)
    events = list(db.scalars(select(AuditEvent).where(AuditEvent.target_id == row.id)))
    assert all(value not in json.dumps([event.metadata_ for event in events]) for value in values)


def test_cross_scope_and_guessed_identity_never_disclose_or_mutate(db, setup):
    result = create(db, setup)
    principal, payload, _ = setup
    scoped_principal = replace(principal, grants=(replace(principal.grants[0], scope_type="site", customer_id=uuid.uuid4(), site_id=uuid.uuid4()),))
    for identifier in [result["id"], uuid.uuid4()]:
        with pytest.raises(HTTPException) as error:
            routes.integration_detail(identifier, scoped_principal, db)
        assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.create_integration(payload, request(), scoped_principal, db))
    assert error.value.status_code == 404
    viewer = replace(principal, grants=(replace(principal.grants[0], permissions=frozenset({"integrations.view"})),))
    with pytest.raises(HTTPException) as error:
        routes.replace_credentials(result["id"], routes.Credentials(values={}), request(), viewer, db)
    assert error.value.status_code == 404


def test_credential_replace_failure_preserves_old_revision_clear_revokes(db, setup, monkeypatch):
    result = create(db, setup)
    principal, payload, _ = setup
    row = db.get(Integration, result["id"])
    old = row.credential_reference
    new = routes.Credentials(values={"token_id": "fixture_" + secrets.token_hex(8) + "@pve!probe", "token_secret": secrets.token_urlsafe(32)})
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", "malformed")
    with pytest.raises(HTTPException):
        routes.replace_credentials(row.id, new, request(), principal, db)
    db.refresh(row)
    assert row.credential_reference == old and db.get(IntegrationSecret, old)
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", secrets.token_hex(32))
    # Replacement does not need to reveal/decrypt the old material.
    routes.replace_credentials(row.id, new, request(), principal, db)
    assert row.credential_reference != old and db.get(IntegrationSecret, old) is None
    configured = AtlasEncryptedSecretProvider(db)
    with configured.materialize_for_job(row, uuid.uuid4(), ["token_secret"]) as lease:
        assert list(lease.values) == ["token_secret"]
        assert "token_secret" not in repr(lease)
    assert lease.revoked and lease.values == {}
    new_reference = row.credential_reference
    assert not routes.clear_credentials(row.id, routes.Confirm(confirmed=True), request(), principal, db)["credential_configured"]
    assert db.get(IntegrationSecret, new_reference) is None
    assert row.data_source_id == result["data_source_id"]


def test_datasource_scope_and_one_to_one_database_constraints(db, setup):
    result = create(db, setup)
    row = db.get(Integration, result["id"])
    fields = {column.name: getattr(row, column.name) for column in Integration.__table__.columns}
    fields.update(id=uuid.uuid4(), creation_key=uuid.uuid4(), credential_reference=None)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Integration(**fields))
            db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            row.customer_id = uuid.uuid4()
            db.flush()


def test_test_connection_has_no_discovery_side_effects_exact_identity_and_cleanup(db, setup, monkeypatch):
    result = create(db, setup)
    principal, payload, stored = setup
    counts = {model: db.scalar(select(func.count()).select_from(model)) for model in [Asset, DiscoveryRun, EvidenceRecord]}
    captured = []
    async def probe(reference, config, values, request_id):
        captured.append((reference, values))
        assert set(values) == {"token_id", "token_secret"}
        return {"success": True, "category": "connected", "source_version": "8.4"}
    monkeypatch.setattr(routes.runtime, "test_connection", probe)
    outcome = asyncio.run(routes.test_connection(result["id"], request(), principal, db))
    assert outcome["compatibility"] == "untested"
    assert captured[0][0] == {"connector_id": "proxmox", "version": "0.1.0", "digest": stored.bundle_digest[7:]}
    assert captured[0][1] == {}
    assert counts == {model: db.scalar(select(func.count()).select_from(model)) for model in counts}
    assert lifecycle.connector_usage_count(db, "proxmox") == 1
    routes.update_integration(result["id"], routes.ConnectionUpdate(enabled=False), request(), principal, db)
    assert lifecycle.connector_usage_count(db, "proxmox") == 1
    routes.retire_integration(result["id"], routes.Confirm(confirmed=True), request(), principal, db)
    assert lifecycle.connector_usage_count(db, "proxmox") == 0
    assert db.get(DataSource, result["data_source_id"])


def test_rewrap_preserves_credentials_and_bad_context_or_key_fails_closed(db, setup):
    result = create(db, setup)
    row = db.get(Integration, result["id"])
    record = db.get(IntegrationSecret, row.credential_reference)
    source = bytes.fromhex(os.environ["ATLAS_DATA_ENCRYPTION_KEY"])
    target = secrets.token_bytes(32)
    original = decrypt_fields(record, source, record.encrypted_fields)
    before = deepcopy(record.encrypted_fields)
    assert rewrap_integrations(db, source, target) == 2
    record = db.get(IntegrationSecret, record.id)
    assert decrypt_fields(record, target, record.encrypted_fields) == original
    assert record.encrypted_fields != before
    with pytest.raises(BackupError):
        with db.begin_nested():
            rewrap_integrations(db, source, target)
    with pytest.raises(SecretProviderError):
        record.integration_id = uuid.uuid4()
        decrypt_fields(record, target, record.encrypted_fields)


def test_mapping_is_exact_global_and_optional_ignore_is_explicit(db, setup, monkeypatch):
    from types import SimpleNamespace
    from app.services import connector_mappings as mappings, connector_catalogue
    from tests.test_connector_packages import manifest as legacy_manifest
    principal, _, _ = setup
    key = "i2_" + uuid.uuid4().hex
    asset_type = AssetType(key=key, name="Fixture " + key, active=True)
    db.add(asset_type)
    db.flush()
    manifest = legacy_manifest()
    manifest["object_classes"] = [{"key": "proxmox.host", "kind": "asset", "label": asset_type.name,
        "required": True, "recommended_asset_type_key": key + "_unknown"}]
    manifest["relationship_classes"] = manifest["facts"] = []
    manifest["discovery_scopes"][0]["object_classes"] = ["proxmox.host"]
    assert not mappings.mapping_state(db, manifest, auto_map=True)[0]["resolved"]
    with pytest.raises(ValueError):
        mappings.require_resolved(db, manifest)
    manifest["object_classes"][0]["recommended_asset_type_key"] = key
    assert mappings.mapping_state(db, manifest, auto_map=True)[0]["target_key"] == key
    monkeypatch.setattr(connector_catalogue, "catalogue", SimpleNamespace(get=lambda *args: SimpleNamespace(manifest=manifest)))
    scoped_admin = replace(principal, grants=(replace(principal.grants[0], scope_type="site", customer_id=uuid.uuid4(), site_id=uuid.uuid4()),))
    payload = routes.MappingInput(version=manifest["version"], kind="asset", source_key="proxmox.host", target_key=key)
    with pytest.raises(HTTPException) as error:
        routes.resolve_mapping("proxmox", payload, request(), scoped_admin, db)
    assert error.value.status_code == 403
    assert routes.resolve_mapping("proxmox", payload, request(), principal, db)["mappings"][0]["resolved"]
    ignored = routes.MappingInput(version=manifest["version"], kind="asset", source_key="proxmox.host", ignored=True)
    with pytest.raises(HTTPException):
        routes.resolve_mapping("proxmox", ignored, request(), principal, db)
    manifest["object_classes"][0]["required"] = False
    assert routes.resolve_mapping("proxmox", ignored, request(), principal, db)["mappings"][0]["ignored"]


def test_update_missing_new_credential_preserves_current_identity_without_decryption(db, setup, monkeypatch):
    from dataclasses import replace as replace_package
    result = create(db, setup)
    _, _, stored = setup
    changed = deepcopy(stored.manifest)
    changed["version"] = "0.2.0"
    changed["connection_fields"].append({"key": "new_credential", "label": "New credential", "type": "secret", "secret": True, "required": True})
    changed["distribution"]["bundle_digest"] = "sha256:" + "b" * 64
    candidate = replace_package(stored, version="0.2.0", bundle_digest=changed["distribution"]["bundle_digest"], manifest=changed,
        verification={**stored.verification, "bundle_digest": changed["distribution"]["bundle_digest"]})
    monkeypatch.setattr("app.services.integration_secrets.decrypt_fields", lambda *a: pytest.fail("update validation read plaintext"))
    with pytest.raises(ValueError):
        lifecycle.activate(db, candidate, healthy_runtime(baseline_id="atlas-ansible-i1-v1", baseline_digest="b" * 64))
    row = db.get(Integration, result["id"])
    assert row.connector_version == "0.1.0" and row.connector_digest == stored.bundle_digest[7:]


def test_global_update_preflight_blocks_configuration_change_without_scope_leak(db, setup, monkeypatch):
    from app.routes.integrations import catalogue_entries
    result = create(db, setup)
    principal, _, stored = setup
    changed = deepcopy(stored.manifest)
    changed['version'] = '0.2.0'
    changed['connection_fields'].append({'key': 'new_credential', 'label': 'New credential', 'type': 'secret', 'secret': True, 'required': True})
    from types import SimpleNamespace
    monkeypatch.setattr(catalogue, 'entries', lambda **kwargs: [{'connector_id': 'proxmox', 'version': '0.2.0', 'state': 'update_available', 'supported_actions': ['update']}])
    monkeypatch.setattr(catalogue, 'get', lambda *args: SimpleNamespace(manifest=changed))
    monkeypatch.setattr('app.services.integration_secrets.decrypt_fields', lambda *a: pytest.fail('preflight read plaintext'))
    entry = catalogue_entries(db, principal, {})[0]
    assert entry['state'] == 'update_requires_configuration' and entry['supported_actions'] == []
    assert str(result['id']) not in json.dumps(entry)
    scoped_viewer = make_principal('integrations.view')
    assert catalogue_entries(db, scoped_viewer, {})[0]['state'] == 'update_available'


def test_disable_preserves_safe_last_probe_and_datasource(db, setup):
    result = create(db, setup)
    row = db.get(Integration, result['id'])
    from datetime import datetime, timezone
    row.last_test_at = datetime.now(timezone.utc)
    row.last_test_status = 'connected'
    row.source_version = '8.4'
    db.commit()
    routes.update_integration(row.id, routes.ConnectionUpdate(enabled=False), request(), setup[0], db)
    assert row.last_test_status == 'connected' and row.source_version == '8.4'
    assert row.data_source_id == result['data_source_id']
    assert db.scalar(select(AuditEvent.id).where(AuditEvent.event_type == 'integration.disabled'))
