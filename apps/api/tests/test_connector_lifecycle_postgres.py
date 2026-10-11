"""Real PostgreSQL active-state invariants, scoped configured visibility and usage."""
from dataclasses import replace
from datetime import datetime, timezone
import os
import secrets
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.authorization import ActiveContext
from app.models import Customer, InstalledConnectorPackage, Integration, Site, Workspace
from app.routes.integrations import configured_integrations
from app.services import connector_lifecycle as lifecycle
from app.services.connector_store import PackageStore
from tests.test_administration import make_principal
from tests.test_connector_packages import bundle

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def db():
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection) as session:
            yield session
        transaction.rollback()
    engine.dispose()


def healthy():
    return {"status": "healthy", "baseline_id": "atlas-ansible-i1-v1", "baseline_digest": "b" * 64}


def test_active_row_replaces_version_and_preserves_exact_identity(db, tmp_path):
    package, verifier, _ = bundle(tmp_path)
    stored = PackageStore(tmp_path / "store").install(package, verifier)
    record = lifecycle.activate(db, stored, healthy())
    assert record.bundle_digest == package.bundle_digest[7:]
    assert record.verification_status == "verified"
    assert db.scalar(select(InstalledConnectorPackage)) is record
    assert lifecycle.activate(db, stored, healthy()) is record
    assert len(list(db.scalars(select(InstalledConnectorPackage)))) == 1
    bad = replace(stored, verification={**stored.verification, "status": "unverified"})
    with pytest.raises(ValueError):
        lifecycle.activate(db, bad, healthy())
    assert record.bundle_digest == package.bundle_digest[7:]
    bad_identity = replace(stored, connector_id="another")
    with pytest.raises(ValueError):
        lifecycle.activate(db, bad_identity, healthy())
    assert len(list(db.scalars(select(InstalledConnectorPackage)))) == 1


def test_primary_key_and_verified_check_cannot_allow_two_active_or_unverified_rows(db, tmp_path):
    package, verifier, _ = bundle(tmp_path)
    stored = PackageStore(tmp_path / "store").install(package, verifier)
    record = lifecycle.activate(db, stored, healthy())
    fields = {col.name: getattr(record, col.name) for col in InstalledConnectorPackage.__table__.columns}
    with db.begin_nested():
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(InstalledConnectorPackage(**fields))
                db.flush()
    fields.update(connector_id="unverified", verification_status="pending")
    with db.begin_nested():
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(InstalledConnectorPackage(**fields))
                db.flush()
    assert db.get(InstalledConnectorPackage, "proxmox").bundle_digest == stored.bundle_digest[7:]


def make_integration(db, name, status="pending"):
    workspace = Workspace(name=name, slug=uuid.uuid4().hex)
    db.add(workspace)
    db.flush()
    customer = Customer(name=name, workspace_id=workspace.id)
    db.add(customer)
    db.flush()
    site = Site(name="Site " + name, customer_id=customer.id)
    db.add(site)
    db.flush()
    integration = Integration(name=name, customer_id=customer.id, site_id=site.id,
        plugin_id="proxmox", base_url="https://example.test", username_or_token_id="test-identity",
        secret_reference="opaque-reference-" + secrets.token_hex(12), verify_tls=True, status=status)
    db.add(integration)
    db.flush()
    return integration


def test_disabled_connections_block_uninstall_and_scoped_list_never_leaks_hidden_tenant(db):
    visible = make_integration(db, "Visible", "disabled")
    hidden = make_integration(db, "Hidden")
    principal = make_principal("integrations.view")
    principal = replace(principal, grants=(replace(principal.grants[0], scope_type="site",
        customer_id=visible.customer_id, site_id=visible.site_id),))
    records = configured_integrations(ActiveContext(None, None), principal, db)
    assert len(records) == 1 and records[0]["id"] == visible.id
    assert records[0]["customer_name"] == "Visible"
    assert {"base_url", "secret_reference", "username_or_token_id"}.isdisjoint(records[0])
    assert lifecycle.connector_usage_count(db, "proxmox") == 2
    with pytest.raises(lifecycle.ConnectorInUse):
        lifecycle.require_unused(db, "proxmox")
    db.delete(hidden)
    db.flush()
    assert lifecycle.connector_usage_count(db, "proxmox") == 1
    with pytest.raises(lifecycle.ConnectorInUse):
        lifecycle.require_unused(db, "proxmox")


def test_activation_transaction_failure_retains_previous_identity(db, tmp_path):
    package, verifier, _ = bundle(tmp_path)
    store = PackageStore(tmp_path / "store")
    stored = store.install(package, verifier)
    active = lifecycle.activate(db, stored, healthy())
    original = lifecycle.installed_response(active)
    with pytest.raises(RuntimeError):
        with db.begin_nested():
            active.bundle_digest = "c" * 64
            db.flush()
            raise RuntimeError("simulated transaction failure")
    db.refresh(active)
    assert lifecycle.installed_response(active) == original
    assert store.verify_connector(package.connector_id, package.version, package.bundle_digest)["state"] == "verified"
