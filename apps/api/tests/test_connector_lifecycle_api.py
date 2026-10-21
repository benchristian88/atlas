"""Real PostgreSQL package lifecycle through the I1 route orchestration.

The catalogue contains inert trusted test archives. Runtime inspection reads the
actual store with the independently deployed verifier; health and transport are
deterministic. No source systems, credentials, jobs or discovery are exercised.
"""
import asyncio
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace
import uuid

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (AuditEvent, Customer, DataSource, DiscoveryRun, EvidenceRecord,
    InstalledConnectorPackage, KnowledgeAssertion, Site, Workspace)
from app.routes import integrations as routes
from app.services import connector_catalogue, connector_lifecycle as lifecycle
from app.services.connector_catalogue import CatalogueUnavailable
from app.services.connector_store import PackageStore
from app.services.connector_verification import BootstrapReleaseVerifier, OfficialBundleVerifier
from tests.test_administration import make_principal, request
from tests.test_connector_lifecycle_postgres import make_integration
from tests.test_connector_packages import bundle, path_for, runtime as healthy_runtime

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/runtime/ansible"))
from atlas_runtime.server import Runtime

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"),
    reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def db():
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True)
    with engine.connect() as connection:
        transaction = connection.begin()
        # Route-level commits/rollbacks affect savepoints while the outer test
        # transaction always restores the disposable database's starting state.
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def harness(db, tmp_path, monkeypatch):
    principal = make_principal("integration_runtime.manage", "integration_runtime.view")
    principal.user.email = "i1-lifecycle-" + uuid.uuid4().hex + "@example.test"
    db.add(principal.user)
    db.commit()
    packages = {}
    for version in ("1.0.0", "1.1.0"):
        directory = tmp_path / version
        directory.mkdir()
        package, _, _ = bundle(directory, version=version)
        packages[version] = package
    verifier = OfficialBundleVerifier(BootstrapReleaseVerifier(frozenset(
        (package.connector_id, package.version, package.bundle_digest) for package in packages.values()),
        "inert-api-lifecycle-test"))

    class TrustedTestCatalogue:
        def get(self, connector_id, version):
            if connector_id != "proxmox" or version not in packages:
                raise CatalogueUnavailable("connector_not_in_catalogue")
            return packages[version]

        def verifier(self):
            return verifier

    store = PackageStore(tmp_path / "store")
    independent = Runtime(secrets.token_hex(48), store.root, "development")
    health = healthy_runtime(baseline_id="atlas-ansible-i1-v1", baseline_digest="b" * 64)
    state = SimpleNamespace(principal=principal, packages=packages, store=store,
                            health=health, reject_runtime=False, references=[])

    async def report_health():
        return deepcopy(state.health)

    async def verify_reference(reference):
        state.references.append(deepcopy(reference))
        if state.reject_runtime:
            return {**reference, "state": "unavailable"}
        return independent.verify_connector(reference)

    monkeypatch.setattr(connector_catalogue, "catalogue", TrustedTestCatalogue())
    monkeypatch.setattr(lifecycle, "package_store", lambda: store)
    monkeypatch.setattr(routes.runtime, "health", report_health)
    monkeypatch.setattr(routes.runtime, "verify_connector", verify_reference)
    return state


def install(db, harness, version="1.0.0", *, digest=None):
    selection = routes.PackageSelection(version=version,
        digest=digest or harness.packages[version].bundle_digest.removeprefix("sha256:"))
    return asyncio.run(routes._install("proxmox", selection, request(), harness.principal, db))


def uninstall(db, harness):
    return routes.uninstall_connector("proxmox", request(), harness.principal, db)


def active_identity(db):
    row = db.get(InstalledConnectorPackage, "proxmox")
    return (row.version, row.bundle_digest) if row is not None else None


@pytest.mark.parametrize("authenticate", [False, True])
def test_catalogue_validation_does_not_authorize_api_install_or_change_active_state(db, harness, authenticate):
    from app.services.official_catalogue import parse_official_catalogue
    from tests.test_official_catalogue import FIXTURE

    install(db, harness)
    before = active_identity(db)
    existing_audits = len(audits(db, harness))
    before_files = {str(path.relative_to(harness.store.root)): path.read_bytes()
                    for path in harness.store.root.rglob("*") if path.is_file()}
    parsed = parse_official_catalogue(FIXTURE.read_bytes())
    if authenticate:
        from app.services.connector_verification import GithubSigstoreVerifier
        evidence = GithubSigstoreVerifier().verify_catalogue(
            parsed.source_bytes, FIXTURE.with_name("catalogue.sigstore.json").read_bytes())
        assert evidence.artifact_sha256 == "55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd"
    manifest = parsed.document["entries"][0]["manifest"]
    selection = routes.PackageSelection(version=manifest["version"],
        digest=manifest["distribution"]["bundle_digest"][7:])
    # The API still resolves only its approved provider. Neither B1.1 structure
    # nor genuine B1.2 provenance registers entries or authorizes installation.
    with pytest.raises(HTTPException) as caught:
        asyncio.run(routes._install(manifest["id"], selection, request(), harness.principal, db))
    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "connector_not_in_catalogue"
    assert active_identity(db) == before
    assert len(audits(db, harness)) == existing_audits
    assert {str(path.relative_to(harness.store.root)): path.read_bytes()
            for path in harness.store.root.rglob("*") if path.is_file()} == before_files


def audits(db, harness):
    return list(db.scalars(select(AuditEvent).where(AuditEvent.user_id == harness.principal.user.id,
                                                  AuditEvent.target_type == "connector_package")))


def retained_history(db):
    """Populate existing knowledge models without running discovery or ingestion."""
    workspace = Workspace(name="Retained history", slug="retained-" + uuid.uuid4().hex)
    db.add(workspace)
    db.flush()
    customer = Customer(name="Retained history", workspace_id=workspace.id)
    db.add(customer)
    db.flush()
    site = Site(name="Retained site", customer_id=customer.id)
    db.add(site)
    db.flush()
    source = DataSource(customer_id=customer.id, site_id=site.id, name="Historical fixture", source_type="manual")
    db.add(source)
    db.flush()
    run = DiscoveryRun(customer_id=customer.id, site_id=site.id, data_source_id=source.id,
                       status="completed", summary={"fixture": "retained history"})
    db.add(run)
    db.flush()
    now = datetime.now(timezone.utc)
    evidence = EvidenceRecord(discovery_run_id=run.id, data_source_id=source.id, customer_id=customer.id,
        site_id=site.id, entity_kind="asset", payload_json={"fixture": "historical evidence"}, observed_at=now)
    db.add(evidence)
    db.flush()
    assertion = KnowledgeAssertion(customer_id=customer.id, site_id=site.id,
        subject_type="asset", subject_external_id="retained-fixture", predicate="status", value_json="known",
        truth_classification="observed", data_source_id=source.id, discovery_run_id=run.id,
        evidence_record_id=evidence.id, first_observed_at=now, last_observed_at=now, is_accepted=True)
    db.add(assertion)
    db.commit()
    records = (source, run, evidence, assertion)
    return [(type(record), record.id, {column.key: deepcopy(getattr(record, column.key))
             for column in record.__table__.columns}) for record in records]


def assert_history_preserved(db, snapshots):
    db.expire_all()
    for model, identity, values in snapshots:
        record = db.get(model, identity)
        assert record is not None
        assert {column.key: getattr(record, column.key) for column in record.__table__.columns} == values


def test_install_update_rollback_uninstall_preserves_exact_audit_and_knowledge_history(db, harness):
    history = retained_history(db)
    first = install(db, harness)
    assert first["version"] == "1.0.0"
    assert first["digest"] == harness.packages["1.0.0"].bundle_digest[7:]
    second = install(db, harness, "1.1.0")
    assert second["version"] == "1.1.0"
    assert db.scalar(select(func.count()).select_from(InstalledConnectorPackage)) == 1
    rollback = install(db, harness, "1.0.0")
    assert rollback["digest"] == first["digest"]
    assert active_identity(db) == ("1.0.0", first["digest"])
    removed = uninstall(db, harness)
    assert removed == {"status": "removed", "cleanup_pending": False, "connector_id": "proxmox",
                       "version": "1.0.0", "digest": first["digest"]}
    assert active_identity(db) is None
    assert not path_for(harness.store, harness.packages["1.0.0"]).exists()
    assert not path_for(harness.store, harness.packages["1.1.0"]).exists()
    assert not (harness.store.root / "proxmox").exists()
    events = audits(db, harness)
    assert Counter((event.event_type, event.metadata_["version"], event.metadata_["digest"]) for event in events) == Counter({
        ("connector.activated", "1.0.0", first["digest"]): 2,
        ("connector.activated", "1.1.0", second["digest"]): 1,
        ("connector.uninstalled", "1.0.0", first["digest"]): 1})
    assert all(event.metadata_["connector_id"] == "proxmox" and event.success for event in events)
    assert all(set(event.metadata_) == {"connector_id", "version", "digest"} for event in events)
    assert_history_preserved(db, history)


def test_wrong_selected_digest_cannot_replace_active_identity_or_create_audit(db, harness):
    original = install(db, harness)
    with pytest.raises(HTTPException) as rejected:
        install(db, harness, "1.1.0", digest="f" * 64)
    assert rejected.value.status_code == 409
    assert active_identity(db) == (original["version"], original["digest"])
    assert len(audits(db, harness)) == 1
    assert not path_for(harness.store, harness.packages["1.1.0"]).exists()


@pytest.mark.parametrize("runtime_state", ["incompatible", "unavailable", "baseline_mismatch"])
def test_incompatible_or_unavailable_runtime_keeps_previous_version_active(db, harness, runtime_state):
    original = install(db, harness)
    if runtime_state == "baseline_mismatch":
        harness.health["baseline_version"] = "2.0.0"
    else:
        harness.health["status"] = runtime_state
    with pytest.raises(HTTPException) as rejected:
        install(db, harness, "1.1.0")
    assert rejected.value.status_code == 409
    assert active_identity(db) == (original["version"], original["digest"])
    assert len(audits(db, harness)) == 1
    assert not path_for(harness.store, harness.packages["1.1.0"]).exists()


def test_independent_runtime_rejection_cannot_activate_new_store_publication(db, harness):
    original = install(db, harness)
    harness.reject_runtime = True
    with pytest.raises(HTTPException) as rejected:
        install(db, harness, "1.1.0")
    assert rejected.value.status_code == 409
    assert active_identity(db) == (original["version"], original["digest"])
    assert len(audits(db, harness)) == 1
    assert harness.store.verify_connector("proxmox", "1.0.0", harness.packages["1.0.0"].bundle_digest)["state"] == "verified"
    assert harness.references[-1]["version"] == "1.1.0"


def test_database_activation_failure_rolls_back_identity_and_audit_together(db, harness, monkeypatch):
    original = install(db, harness)

    def fail_commit():
        db.flush()
        raise SQLAlchemyError("injected transaction failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(HTTPException) as rejected:
        install(db, harness, "1.1.0")
    assert rejected.value.status_code == 409
    assert active_identity(db) == (original["version"], original["digest"])
    assert len(audits(db, harness)) == 1
    assert "injected" not in str(rejected.value.detail)


def test_database_uninstall_failure_restores_quarantined_package_and_authority(db, harness, monkeypatch):
    original = install(db, harness)
    install(db, harness, "1.1.0")
    install(db, harness, "1.0.0")

    def fail_commit():
        db.flush()
        raise SQLAlchemyError("injected transaction failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(HTTPException) as rejected:
        uninstall(db, harness)
    assert rejected.value.status_code == 409
    assert active_identity(db) == (original["version"], original["digest"])
    assert len(audits(db, harness)) == 3
    assert harness.store.verify_connector("proxmox", "1.0.0", harness.packages["1.0.0"].bundle_digest)["state"] == "verified"
    assert harness.store.verify_connector("proxmox", "1.1.0", harness.packages["1.1.0"].bundle_digest)["state"] == "verified"
    assert not list(harness.store.root.glob(".removed-*"))


@pytest.mark.parametrize("status", ["pending", "disabled"])
def test_live_configured_and_disabled_usage_blocks_update_and_uninstall(db, harness, status):
    original = install(db, harness)
    integration = make_integration(db, "Configured guard", status)
    db.commit()
    for action in (lambda: install(db, harness, "1.1.0"), lambda: uninstall(db, harness)):
        with pytest.raises(HTTPException) as rejected:
            action()
        assert rejected.value.status_code == 409
        assert "configured connections" in rejected.value.detail
        assert active_identity(db) == (original["version"], original["digest"])
        assert len(audits(db, harness)) == 1
    assert db.get(type(integration), integration.id).status == status
    assert harness.store.verify_connector("proxmox", "1.0.0", harness.packages["1.0.0"].bundle_digest)["state"] == "verified"
