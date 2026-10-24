"""Pure lifecycle tests and disposable PostgreSQL state-machine regression.

Storage tests deliberately use labelled NON-AUTHENTICATED evidence at the private
persistence primitive. They do not fabricate verifier success. Pipeline tests use
real cryptography and must fail publication policy for the current release.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from dataclasses import replace
import hashlib
import json
import os
from types import SimpleNamespace
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.authorization import get_principal
from app.database import get_db
from app.models import AuditEvent, ConnectorCatalogueRevision as Revision, ConnectorCatalogueState as State, InstalledConnectorPackage
from app.routes import integrations as routes
from app.services import catalogue_source as source, trusted_catalogue as consumer
from app.services.backup_archive import BackupError
from app.services.connector_catalogue import accepted_official_metadata, catalogue
from app.services.official_catalogue import parse_official_catalogue
from tests.test_administration import make_principal, request
from tests.test_catalogue_source import RAW, BUNDLE, DIGEST, http_fixture

STORAGE_ONLY = {"test_boundary": "unauthenticated storage unit fixture; NOT verifier evidence"}


def changed(sequence=2, mutate=None):
    document = json.loads(RAW)
    document["sequence"] = sequence
    if mutate:
        mutate(document)
    raw = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode()
    return parse_official_catalogue(raw).source_bytes


def future(document):
    entry = deepcopy(document["entries"][0])
    m = entry["manifest"]
    m["id"] = "future-example"
    m["version"] = "1.0.0"
    entry["release_tag"] = "future-example-v1.0.0"
    entry["release_asset_id"] += 1
    m["distribution"]["asset_uri"] = f"https://github.com/{source.REPOSITORY}/releases/download/future-example-v1.0.0/future-example-1.0.0.tar.gz"
    document["entries"].append(entry)
    document["entries"].sort(key=lambda e: (e["manifest"]["id"], e["manifest"]["version"]))


def test_generic_future_connector_and_withdrawal_history():
    document = parse_official_catalogue(changed(mutate=future)).document
    history = consumer.history_after(document, {})
    assert "future-example/1.0.0" in history
    document["entries"][0]["status"] = "withdrawn"
    history = consumer.history_after(document, history)
    omitted = {**document, "entries": document["entries"][1:]}
    retained = consumer.history_after(omitted, history)
    assert retained["future-example/1.0.0"]["withdrawn"]
    document["entries"][0]["status"] = "active"
    with pytest.raises(source.SourceError, match="withdrawal_reactivated"):
        consumer.history_after(document, retained)


@pytest.mark.parametrize("field", ["manifest", "digest", "tag", "asset"])
def test_immutable_identity_changes(field):
    d = json.loads(RAW)
    history = consumer.history_after(d, {})
    e = d["entries"][0]
    if field == "manifest":
        e["manifest"]["name"] = "Changed display metadata"
    elif field == "digest":
        e["manifest"]["distribution"]["bundle_digest"] = "sha256:" + "a" * 64
    elif field == "tag":
        e["release_tag"] += "-changed"
    else:
        e["release_asset_id"] += 1
    with pytest.raises(source.SourceError, match="historical_identity_changed"):
        consumer.history_after(d, history)


def test_sequence_and_bootstrap_policy():
    document = json.loads(RAW)
    state = SimpleNamespace(highest_sequence=None, highest_digest=None)
    assert consumer.transition(document, DIGEST, state) == "accepted"
    with pytest.raises(source.SourceError, match="bootstrap_policy_rejected"):
        consumer.transition(document, "a" * 64, state)
    state.highest_sequence, state.highest_digest = 1, DIGEST
    assert consumer.transition(document, DIGEST, state) == "unchanged"
    with pytest.raises(source.SourceError, match="catalogue_substitution"):
        consumer.transition(document, "a" * 64, state)
    state.highest_sequence = 2
    with pytest.raises(source.SourceError, match="catalogue_rollback"):
        consumer.transition(document, DIGEST, state)
    document["sequence"] = 3
    assert consumer.transition(document, "a" * 64, state) == "accepted"


@pytest.fixture
def db(tmp_path, monkeypatch):
    url = os.getenv("ATLAS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires disposable migrated PostgreSQL")
    monkeypatch.setenv("ATLAS_STATE_DIR", str(tmp_path / "state"))
    engine = create_engine(url, hide_parameters=True)
    with engine.connect() as connection:
        outer = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as session:
            yield session
        outer.rollback()
    engine.dispose()


def store(db, raw=RAW, confirmed=None):
    state = consumer._lock(db)
    result = consumer._store_revision(db, state, raw, STORAGE_ONLY, STORAGE_ONLY, confirmed or source.utcnow())
    db.commit()
    return result


def allow_attempt(db):
    s = db.get(State, 1)
    s.next_attempt_at = source.utcnow() - timedelta(seconds=1)
    db.commit()


def test_first_unchanged_higher_restart_and_projection(db):
    assert consumer.status(db)["trusted_remote_available"] is False
    before = catalogue._load()[0]
    assert store(db) == "accepted"
    first = db.get(Revision, 1)
    assert first.original_bytes == RAW and first.content_digest == DIGEST
    earlier = source.utcnow() - timedelta(days=10)
    assert store(db, confirmed=earlier) == "unchanged"
    assert db.scalar(select(func.count()).select_from(Revision)) == 1
    newer = changed(mutate=future)
    assert store(db, newer) == "accepted"
    assert db.scalar(select(func.count()).select_from(Revision)) == 2
    db.expire_all()
    assert consumer.status(db)["sequence"] == 2
    assert consumer.status(db)["last_confirmed_current_at"] > earlier
    assert consumer.status(db)["generated_at"] < consumer.status(db)["last_confirmed_current_at"]
    projected = accepted_official_metadata(db)
    assert projected[0]["connector_id"] == "future-example"
    assert all(not e["package_available"] and e["supported_actions"] == [] for e in projected)
    assert db.scalar(select(func.count()).select_from(InstalledConnectorPackage)) == 0
    assert catalogue._load()[0] == before
    with Session(bind=db.get_bind(), join_transaction_mode="create_savepoint") as reopened:
        assert consumer.status(reopened)["content_digest"] == hashlib.sha256(newer).hexdigest()


def test_store_rejects_lower_substitution_malformed_and_preserves_history(db):
    store(db)
    store(db, changed())
    for raw, code in [(RAW, "catalogue_rollback"), (changed() + b"\n", "catalogue_substitution"),
                      (b'{"sequence":3}', "invalid_catalogue_fields")]:
        with pytest.raises(Exception, match=code):
            store(db, raw)
        db.rollback()
        assert consumer.status(db)["sequence"] == 2
        assert db.scalar(select(func.count()).select_from(Revision)) == 2


def test_database_revision_and_checkpoint_guards(db):
    store(db)
    for sql in ["UPDATE connector_catalogue_revisions SET original_bytes = 'x'",
                "DELETE FROM connector_catalogue_revisions", "DELETE FROM connector_catalogue_state",
                "UPDATE connector_catalogue_state SET highest_sequence=NULL, highest_digest=NULL"]:
        with pytest.raises(SQLAlchemyError):
            db.execute(text(sql))
        db.rollback()
    assert consumer.status(db)["sequence"] == 1


def test_lease_coalescing_recovery_and_lost_owner(db):
    first, result = consumer.claim(db)
    assert result == "claimed"
    assert consumer.claim(db) == (None, "in_progress")
    state = db.get(State, 1)
    state.lease_until = source.utcnow() - timedelta(seconds=1)
    db.commit()
    second, result = consumer.claim(db)
    assert result == "claimed" and second != first
    with pytest.raises(source.SourceError, match="refresh_ownership_lost"):
        consumer._owned(db.get(State, 1), first)


def test_uncommitted_promotion_rolls_back(db):
    store(db)
    state = consumer._lock(db)
    consumer._store_revision(db, state, changed(), STORAGE_ONLY, STORAGE_ONLY, source.utcnow())
    db.flush()
    db.rollback()
    assert consumer.status(db)["sequence"] == 1
    assert db.get(Revision, 2) is None


def test_checkpoint_reconstruction_without_currentness(db):
    store(db)
    # Insert-only retained history models checkpoint restoration/interrupted
    # older implementation. No trigger bypass or invented cryptography.
    raw = changed()
    db.add(Revision(sequence=2, source=source.SOURCE, schema_version="1.0", content_digest=hashlib.sha256(raw).hexdigest(),
        original_bytes=raw, generated_at=source.utcnow(), verification_evidence=STORAGE_ONLY,
        publication_evidence=STORAGE_ONLY, accepted_at=source.utcnow()))
    db.commit()
    consumer.recover_checkpoint(db, db.get(State, 1))
    db.commit()
    assert consumer.status(db)["sequence"] == 2
    assert consumer.status(db)["last_confirmed_current_at"] is None


def test_real_verifier_publication_block_persisted_without_promotion(db, http_fixture):
    outcome = consumer.refresh(db)
    assert outcome["result"] == "failed"
    state = outcome["status"]
    assert state["last_error_code"] == "publication_not_immutable"
    assert state["last_download_at"] and state["last_authenticity_verified_at"]
    assert state["last_confirmed_current_at"] is None
    assert state["trusted_remote_available"] is False
    assert db.scalar(select(func.count()).select_from(Revision)) == 0
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "connector_catalogue.refreshed")).success is False
    assert consumer.refresh(db)["result"] == "cooldown"


@pytest.mark.parametrize("kind", ["transport", "crypto", "publication", "channel"])
def test_failed_refresh_preserves_last_known_good_and_freshness(db, http_fixture, monkeypatch, kind):
    store(db)
    original = consumer.status(db)
    if kind == "transport":
        async def fail(_, **kwargs):
            raise OSError("secret signed download URL must never escape")
        monkeypatch.setattr(source, "retrieve_candidate", fail)
    elif kind == "crypto":
        http_fixture["bundle"]["dsseEnvelope"]["signatures"][0]["sig"] = "invalid"
    elif kind == "channel":
        http_fixture["mutation"] = True
    result = consumer.refresh(db)
    assert result["result"] == "failed"
    assert "secret signed" not in str(result)
    assert result["status"]["sequence"] == 1
    assert result["status"]["last_confirmed_current_at"] == original["last_confirmed_current_at"]
    assert db.get(Revision, 1).original_bytes == RAW


def test_lost_lease_during_network_cannot_finish(db, monkeypatch):
    async def lose(_, **kwargs):
        s = db.get(State, 1)
        s.operation_id = uuid.uuid4()
        db.commit()
        raise source.SourceError("source_timeout")
    monkeypatch.setattr(source, "retrieve_candidate", lose)
    result = consumer.refresh(db)
    assert result["code"] == "refresh_ownership_lost"
    assert db.get(State, 1).operation_id is not None
    assert consumer.status(db)["last_error_code"] is None


def test_restore_marker_during_fetch_blocks_promotion(db, monkeypatch):
    from app.services.backup_runtime import set_maintenance
    async def restore(_, **kwargs):
        set_maintenance(str(uuid.uuid4()), "draining")
        raise source.SourceError("source_timeout")
    monkeypatch.setattr(source, "retrieve_candidate", restore)
    with pytest.raises(BackupError):
        consumer.refresh(db)
    assert db.scalar(select(func.count()).select_from(Revision)) == 0


def test_audit_database_failure_is_atomic(db, http_fixture, monkeypatch):
    store(db)
    def fail(*args, **kwargs):
        raise SQLAlchemyError("private diagnostic")
    monkeypatch.setattr(consumer, "add_audit_event", fail)
    result = consumer.refresh(db)
    assert result == {"result": "failed", "code": "catalogue_persistence_failed"}
    assert consumer.status(db)["sequence"] == 1
    assert consumer.status(db)["last_download_at"] is None
    assert db.get(State, 1).operation_id is not None


def test_global_permissions_and_api_input(db, monkeypatch):
    principal = make_principal("integration_runtime.view", "integration_runtime.manage")
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: principal
    monkeypatch.setattr(consumer, "refresh", lambda *a, **kw: {"result": "in_progress"})
    with TestClient(app) as client:
        assert client.get("/api/integration-catalogue/status").status_code == 200
        assert client.post("/api/integration-catalogue/refresh", json={}).json()["result"] == "in_progress"
        for body in ({"url": "http://127.0.0.1"}, {"repository": "attacker/repo"}, {"signer": "other"}):
            assert client.post("/api/integration-catalogue/refresh", json=body).status_code == 422
        assert client.post("/api/integration-catalogue/refresh?url=bad").status_code == 422
        scoped = replace(principal, grants=(replace(principal.grants[0], scope_type="customer", customer_id=uuid.uuid4()),))
        app.dependency_overrides[get_principal] = lambda: scoped
        assert client.post("/api/integration-catalogue/refresh").status_code == 403
        assert client.get("/api/integration-catalogue/status").status_code == 403
        def unauthenticated():
            raise HTTPException(401, "Authentication required")
        app.dependency_overrides[get_principal] = unauthenticated
        assert client.post("/api/integration-catalogue/refresh").status_code == 401


def test_concurrent_real_transactions_coalesce():
    url = os.getenv("ATLAS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires disposable migrated PostgreSQL")
    engine = create_engine(url, hide_parameters=True)
    with engine.begin() as conn:
        assert conn.scalar(select(func.count()).select_from(Revision)) == 0, "isolated empty catalogue required"
        conn.execute(text("UPDATE connector_catalogue_state SET operation_id=NULL, lease_until=NULL, next_attempt_at=NULL"))
    def run():
        with Session(engine) as db:
            return consumer.claim(db)[1]
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: run(), range(4)))
        assert sorted(results) == ["claimed", "in_progress", "in_progress", "in_progress"]
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE connector_catalogue_state SET operation_id=NULL, lease_until=NULL, next_attempt_at=NULL, last_attempt_at=NULL"))
        engine.dispose()


def test_new_version_incompatibility_and_withdrawal_persist_without_install(db):
    store(db)
    def version(document):
        entry = deepcopy(document["entries"][0])
        manifest = entry["manifest"]
        manifest["version"] = "99.0.0"
        identifier = manifest["id"]
        entry["release_tag"] = f"{identifier}-v99.0.0"
        entry["release_asset_id"] += 1
        manifest["distribution"]["asset_uri"] = f"https://github.com/{source.REPOSITORY}/releases/download/{entry['release_tag']}/{identifier}-99.0.0.tar.gz"
        manifest["compatibility"]["atlas"] = {"minimum": "99.0.0", "exclusive_maximum": "100.0.0"}
        document["entries"][0]["status"] = "withdrawn"
        document["entries"].append(entry)
    raw = changed(mutate=version)
    store(db, raw)
    d = json.loads(raw)
    old_key = d["entries"][0]["manifest"]["id"] + "/" + d["entries"][0]["manifest"]["version"]
    d["sequence"] = 3
    d["entries"] = d["entries"][1:]
    store(db, json.dumps(d).encode())
    assert db.get(State, 1).identity_history[old_key]["withdrawn"]
    assert db.scalar(select(func.count()).select_from(InstalledConnectorPackage)) == 0


def test_uncommitted_revision_invisible_to_independent_session():
    url = os.getenv("ATLAS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires disposable migrated PostgreSQL")
    engine = create_engine(url, hide_parameters=True)
    try:
        with Session(engine) as writing, Session(engine) as reading:
            assert consumer.status(reading)["trusted_remote_available"] is False
            s = consumer._lock(writing)
            consumer._store_revision(writing, s, RAW, STORAGE_ONLY, STORAGE_ONLY, source.utcnow())
            writing.flush()
            assert consumer.status(reading)["trusted_remote_available"] is False
            assert reading.scalar(select(func.count()).select_from(Revision)) == 0
            writing.rollback()
    finally:
        engine.dispose()


def test_additive_migration_roundtrip_preserves_existing_tables():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from pathlib import Path
    url = os.getenv("ATLAS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires disposable migrated PostgreSQL")
    engine = create_engine(url, hide_parameters=True)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                assert connection.scalar(select(func.count()).select_from(Revision)) == 0
                original = connection.scalar(text("SELECT count(*) FROM integrations"))
                config.attributes["connection"] = connection
                command.downgrade(config, "20261018_0030")
                assert "connector_catalogue_state" not in inspect(connection).get_table_names()
                command.upgrade(config, "head")
                assert connection.scalar(text("SELECT count(*) FROM integrations")) == original
                assert connection.scalar(text("SELECT count(*) FROM connector_catalogue_state")) == 1
                assert connection.scalar(text("SELECT highest_sequence FROM connector_catalogue_state")) is None
                assert {c["name"] for c in inspect(connection).get_columns("connector_catalogue_revisions")} == set(Revision.__table__.columns.keys())
                assert {c["name"] for c in inspect(connection).get_columns("connector_catalogue_state")} == set(State.__table__.columns.keys())
            finally:
                outer.rollback()
    finally:
        engine.dispose()


def test_migration_downgrade_refuses_accepted_history(db):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    store(db)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    config.attributes["connection"] = db.connection()
    with pytest.raises(RuntimeError, match="Retain authenticated catalogue history"):
        command.downgrade(config, "20261018_0030")
    assert db.get(Revision, 1).original_bytes == RAW


def test_authenticated_older_live_candidate_rejected_as_rollback(db, http_fixture):
    store(db)
    store(db, changed())
    previous = consumer.status(db)["last_confirmed_current_at"]
    result = consumer.refresh(db)
    assert result["status"]["last_error_code"] == "catalogue_rollback"
    assert result["status"]["source_conflict"] == "catalogue_rollback"
    assert result["status"]["sequence"] == 2
    assert result["status"]["last_confirmed_current_at"] == previous


def test_higher_sequence_cannot_reuse_genuine_old_attestation(db, http_fixture):
    store(db)
    previous = consumer.status(db)["last_confirmed_current_at"]
    raw = changed()
    http_fixture["raw"] = raw
    for asset in http_fixture["release"]["assets"]:
        asset.update(size=len(raw), digest="sha256:" + hashlib.sha256(raw).hexdigest())
    result = consumer.refresh(db)
    assert result["result"] == "failed"
    assert result["status"]["sequence"] == 1
    assert result["status"]["last_authenticity_verified_at"] is None
    assert result["status"]["last_confirmed_current_at"] == previous


def test_rate_limit_delay_persists_across_sessions(db, monkeypatch):
    async def limited(_, **kwargs):
        raise source.SourceError("source_rate_limited", retry_after=3600)
    monkeypatch.setattr(source, "retrieve_candidate", limited)
    start = source.utcnow()
    result = consumer.refresh(db)
    assert result["status"]["next_attempt_at"] >= start + timedelta(seconds=3600)
    assert result["status"]["last_error_code"] == "source_rate_limited"
    db.expire_all()
    assert consumer.refresh(db)["result"] == "cooldown"
