"""Destructive H3 acceptance ONLY on explicitly supplied disposable databases."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid

from alembic import command
from fastapi.testclient import TestClient
import pyotp
import pytest
from redis import Redis
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.auth import COOKIE_NAME, create_session_token, hash_password, verify_password
from app.database import get_db
from app.main import app
from app.models import (AccessAssignment, Asset, AssetIconCache, AssetInterface, AssetRelationship, AuditEvent,
                        BusinessFunction, CriticalityLevel, Customer, InstallationState, MfaChallenge, MfaRecoveryCode,
                        Network, Role, Service, ServiceAssetDependency, ServiceType, Site,
                        SystemSetting, User, UserMfa, Workspace, RelationshipType)
from app.services import backup_runtime as runtime, backups, mfa
from app.services.backup_archive import BackupError, decrypt_archive, encrypt_archive
from app.services.backup_postgres import migration_config
from app.services.encrypted_data import ENCRYPTED_DATA_ADAPTERS, rewrap_application_data
from app.services.installation import SETUP_COOKIE, reset_setup_code, verify_setup_code
from scripts.seed_system import seed_system

pytestmark = pytest.mark.skipif(not (os.getenv("ATLAS_TEST_H3_SOURCE_URL") and os.getenv("ATLAS_TEST_H3_TARGET_URL")),
                               reason="requires two disposable PostgreSQL databases owned by their Atlas role")


def migrate(engine, revision="head"):
    config = migration_config()
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


@pytest.fixture
def installations(tmp_path, monkeypatch):
    source = create_engine(os.environ["ATLAS_TEST_H3_SOURCE_URL"], hide_parameters=True)
    target = create_engine(os.environ["ATLAS_TEST_H3_TARGET_URL"], hide_parameters=True)
    assert source.url.database != target.url.database
    monkeypatch.setenv("ATLAS_STATE_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("ATLAS_INSTALL_METHOD", "development")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_SECRET_KEY", secrets.token_hex(48))
    monkeypatch.setenv("REDIS_URL", os.getenv("ATLAS_TEST_H3_REDIS_URL", ""))
    source_key, target_key = secrets.token_hex(32), secrets.token_hex(32)
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", source_key)
    migrate(source); migrate(target)
    password, passphrase = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    seed = pyotp.random_base32()
    with Session(source, expire_on_commit=False) as db:
        seed_system(db)
        master = db.scalar(select(Role).where(Role.name == "Master Administrator"))
        user = User(email="h3@example.com", display_name="Portable administrator", password_hash=hash_password(password), mfa_enabled=True)
        db.add(user); db.flush()
        db.add(AccessAssignment(user_id=user.id, role_id=master.id, scope_type="global"))
        active_nonce, active_cipher = mfa.encrypt_seed(user.id, seed)
        pending_nonce, pending_cipher = mfa.encrypt_seed(user.id, seed)
        state = UserMfa(user_id=user.id, secret_nonce=active_nonce, secret_ciphertext=active_cipher,
                        confirmed_at=datetime.now(timezone.utc), pending_nonce=pending_nonce,
                        pending_ciphertext=pending_cipher, pending_id=uuid.uuid4(),
                        pending_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
        db.add(state); db.flush()
        codes = mfa.new_recovery_codes(db, user)
        db.add(MfaChallenge(user_id=user.id, id=uuid.uuid4(), session_version=user.session_version,
                            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)))
        workspace = Workspace(name="H3 workspace", slug="h3")
        db.add(workspace); db.flush()
        customer = Customer(workspace_id=workspace.id, name="Portable customer")
        db.add(customer); db.flush()
        site = Site(customer_id=customer.id, name="Portable site")
        db.add(site); db.flush()
        asset = Asset(workspace_id=workspace.id, customer_id=customer.id, site_id=site.id, name="Portable host", asset_type="server")
        other = Asset(workspace_id=workspace.id, customer_id=customer.id, site_id=site.id, name="Portable VM", asset_type="virtual_machine")
        network = Network(customer_id=customer.id, site_id=site.id, name="Portable LAN", network_type="vlan", vlan_id=77)
        service_type = db.scalar(select(ServiceType).limit(1))
        criticality = db.scalar(select(CriticalityLevel).limit(1))
        service = Service(customer_id=customer.id, site_id=site.id, name="Portable service", slug="portable-service", service_type_id=service_type.id, criticality_level_id=criticality.id)
        function = BusinessFunction(customer_id=customer.id, site_id=site.id, name="Portable function")
        db.add_all([asset, other, network, service, function]); db.flush()
        db.add(AssetInterface(asset_id=asset.id, name="eth0", network_id=network.id, ip_address="10.0.77.1"))
        db.add(AssetRelationship(customer_id=customer.id, site_id=site.id, source_asset_id=other.id,
                                 target_asset_id=asset.id, relationship_type="runs_on"))
        relationship_type = db.scalar(select(RelationshipType).where(RelationshipType.key == "runs_on"))
        db.add(ServiceAssetDependency(customer_id=customer.id, site_id=site.id, service_id=service.id,
                                      asset_id=asset.id, relationship_type_id=relationship_type.id))
        db.add(AssetIconCache(asset_id=asset.id, source_hash="a" * 64, content_hash="b" * 64,
                              attempted_source_hash="a" * 64, attempt_token=uuid.uuid4(),
                              retry_after=datetime.now(timezone.utc), data=b"cached image bytes"))
        db.add(AuditEvent(event_type="h3.fixture", target_type="asset", target_id=asset.id, actor_email=user.email))
        setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "auth.session_minutes"))
        setting.value_ = 123
        installation = db.get(InstallationState, 1)
        installation.initialized_at = datetime.now(timezone.utc)
        installation.setup_generation = 10
        db.commit()
        ids = {"user": user.id, "asset": asset.id, "service": service.id, "function": function.id}
    jobs = backups.BackupJobs(target)
    monkeypatch.setattr(backups, "_jobs", jobs)
    yield dict(source=source, target=target, source_key=source_key, target_key=target_key,
               password=password, passphrase=passphrase, seed=seed, codes=codes,
               ids=ids, jobs=jobs, tmp=tmp_path, monkeypatch=monkeypatch)
    # Terminal status is published before the executor's cleanup finishes.
    # Wait for its lock release before changing process-global fixture env.
    operation_fd = runtime.lock_file("operation.lock", exclusive=True, blocking=True)
    runtime.unlock(operation_fd)
    source.dispose(); target.dispose()
    app.dependency_overrides.clear()


def portable_backup(inst):
    work = inst["tmp"] / "source-work"
    work.mkdir(mode=0o700)
    backups.BackupService(inst["source"]).create(work, inst["passphrase"])
    return work / "backup.atlasbackup"


def restore(inst, archive, *, mode="local", passphrase=None):
    inst["monkeypatch"].setenv("ATLAS_DATA_ENCRYPTION_KEY", inst["target_key"])
    jobs = inst["jobs"]
    job_id, fd, _ = jobs.reserve(kind="restore", owner="local-operator", actor_email="local-operator", mode=mode)
    path = runtime.job_directory(job_id)
    shutil.copyfile(archive, path / "upload.atlasbackup")
    try:
        jobs.service.restore(job_id, passphrase or inst["passphrase"], runtime.job_state(job_id))
    finally:
        marker = runtime.maintenance()
        runtime.remove_work(job_id, keep_recovery=marker is not None)
        runtime.unlock(fd)


def test_fresh_full_state_mfa_portability_target_secrets_and_sessions(installations):
    inst = installations
    archive = portable_backup(inst)
    signing_key = os.environ["AUTH_SECRET_KEY"]
    # A token with the SAME signing key and a colliding restored version must
    # still fail. A generation increment alone cannot guarantee this.
    old_token = create_session_token(inst["ids"]["user"], 2)
    deployment = {"ATLAS_BIND_ADDRESS": "127.0.0.2", "ATLAS_PORT": "3999", "POSTGRES_PASSWORD": secrets.token_hex(24)}
    for key, value in deployment.items():
        inst["monkeypatch"].setenv(key, value)
    environment_file = inst["tmp"] / "target.env"
    environment_file.write_text("target deployment configuration")
    before = environment_file.read_bytes()
    if os.getenv("ATLAS_TEST_H3_REDIS_URL"):
        redis = Redis.from_url(os.environ["ATLAS_TEST_H3_REDIS_URL"])
        redis.set("stale-job", "old database id")
    restore(inst, archive)
    assert runtime.maintenance() is None
    assert os.environ["AUTH_SECRET_KEY"] == signing_key
    assert os.environ["ATLAS_DATA_ENCRYPTION_KEY"] == inst["target_key"]
    assert all(os.environ[key] == value for key, value in deployment.items())
    assert environment_file.read_bytes() == before
    with Session(inst["target"]) as db:
        user = db.get(User, inst["ids"]["user"])
        assert user.email == "h3@example.com" and user.mfa_enabled and verify_password(inst["password"], user.password_hash)
        assert db.get(Asset, inst["ids"]["asset"]).name == "Portable host"
        assert db.get(Service, inst["ids"]["service"]).name == "Portable service"
        assert db.get(BusinessFunction, inst["ids"]["function"]).name == "Portable function"
        for model in (AssetRelationship, ServiceAssetDependency, AssetInterface, Network, AssetIconCache):
            assert db.scalar(select(func.count()).select_from(model)) == 1
        assert db.scalar(select(SystemSetting.value_).where(SystemSetting.key == "auth.session_minutes")) == 123
        assert db.scalar(select(func.count()).select_from(AccessAssignment)) == 1
        assert db.scalar(select(func.count()).select_from(MfaRecoveryCode)) == 12
        assert db.scalar(select(func.count()).select_from(MfaChallenge)) == 0
        state = db.get(UserMfa, user.id)
        assert state.pending_ciphertext is None
        assert mfa.decrypt_seed(user.id, state.secret_nonce, state.secret_ciphertext) == inst["seed"]
        inst["monkeypatch"].setenv("ATLAS_DATA_ENCRYPTION_KEY", inst["source_key"])
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            mfa.decrypt_seed(user.id, state.secret_nonce, state.secret_ciphertext)
        inst["monkeypatch"].setenv("ATLAS_DATA_ENCRYPTION_KEY", inst["target_key"])
        installation = db.get(InstallationState, 1)
        assert installation.initialized_at and installation.setup_code_hash is None
        assert installation.setup_generation == 11
        actions = list(db.scalars(select(AuditEvent.event_type)))
        assert "h3.fixture" in actions and "restore.completed" in actions
    def database():
        with Session(inst["target"], autoflush=False, expire_on_commit=False) as db:
            yield db
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        client.cookies.set(COOKIE_NAME, old_token)
        assert client.get("/api/auth/me").status_code == 401
        assert client.post("/api/auth/login", json={"email": "h3@example.com", "password": inst["password"]}).json()["mfa_required"]
        assert client.post("/api/auth/mfa/verify", json={"code": pyotp.TOTP(inst["seed"]).now()}).status_code == 400
        next_instant = datetime.now(timezone.utc) + timedelta(seconds=31)
        inst["monkeypatch"].setattr(mfa, "now", lambda: next_instant)
        response = client.post("/api/auth/mfa/verify", json={"code": pyotp.TOTP(inst["seed"]).at(next_instant)})
        assert response.status_code == 200
        assert client.get("/api/auth/me").status_code == 200
        assert client.post("/api/setup/verify", json={"code": secrets.token_urlsafe(24)}).status_code == 409
    if os.getenv("ATLAS_TEST_H3_REDIS_URL"):
        assert redis.dbsize() == 0


def test_same_archive_second_target_key_and_overwrite_removes_later_data(installations):
    inst = installations
    archive = portable_backup(inst)
    restore(inst, archive)
    with Session(inst["target"]) as db:
        db.get(Asset, inst["ids"]["asset"]).name = "Changed after backup"
        db.add(SystemSetting(key="later.setting", value_="later"))
        db.commit()
    inst["target_key"] = secrets.token_hex(32)
    restore(inst, archive)
    with Session(inst["target"]) as db:
        state = db.get(UserMfa, inst["ids"]["user"])
        assert mfa.decrypt_seed(state.user_id, state.secret_nonce, state.secret_ciphertext) == inst["seed"]
        assert db.get(Asset, inst["ids"]["asset"]).name == "Portable host"
        assert db.scalar(select(SystemSetting).where(SystemSetting.key == "later.setting")) is None


@pytest.mark.parametrize("failure", ["password", "corrupt", "schema"])
def test_preflight_failure_makes_no_database_changes(installations, failure):
    inst = installations
    archive = portable_backup(inst)
    with Session(inst["target"]) as db:
        db.add(SystemSetting(key="unchanged", value_="sentinel")); db.commit()
    if failure == "corrupt":
        value = bytearray(archive.read_bytes()); value[-1] ^= 1; archive.write_bytes(value)
    if failure == "schema":
        work = inst["tmp"] / "opened"; work.mkdir()
        opened = decrypt_archive(archive, work, inst["passphrase"])
        metadata = opened.manifest.model_dump(exclude={"components"})
        metadata["source_revision"] = "unknown_future"
        archive.unlink()
        encrypt_archive(opened.dump, archive, inst["passphrase"], opened.source_key, metadata)
    with pytest.raises(BackupError):
        restore(inst, archive, passphrase=secrets.token_urlsafe(24) if failure == "password" else None)
    assert runtime.maintenance() is None
    with Session(inst["target"]) as db:
        assert db.scalar(select(SystemSetting.value_).where(SystemSetting.key == "unchanged")) == "sentinel"
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 0
        assert db.scalar(select(func.count()).select_from(User)) == 0


def test_failure_after_replace_automatically_recovers_original_database(installations):
    inst = installations
    archive = portable_backup(inst)
    with Session(inst["target"]) as db:
        db.add(SystemSetting(key="rollback.sentinel", value_="original")); db.commit()
    inst["monkeypatch"].setattr(inst["jobs"].service, "post_restore", lambda *args: (_ for _ in ()).throw(BackupError("Injected validation failure")))
    with pytest.raises(BackupError, match="original Atlas data was recovered"):
        restore(inst, archive)
    assert runtime.maintenance() is None
    with Session(inst["target"]) as db:
        assert db.scalar(select(SystemSetting.value_).where(SystemSetting.key == "rollback.sentinel")) == "original"
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert "restore.rollback_completed" in list(db.scalars(select(AuditEvent.event_type)))


def test_failed_rollback_crash_restart_keeps_encrypted_recovery_and_fail_closed(installations):
    inst = installations
    archive = portable_backup(inst)
    service = inst["jobs"].service
    original_replace = service.postgres.replace
    inst["monkeypatch"].setattr(service.postgres, "replace", lambda *args: (_ for _ in ()).throw(BackupError("Injected database failure")))
    with pytest.raises(BackupError, match="local recovery is required"):
        restore(inst, archive)
    marker = runtime.maintenance()
    assert marker["phase"] == "recovery_required"
    work = runtime.job_directory(marker["job_id"])
    assert (work / "rollback.atlasbackup").exists()
    assert not list(work.glob("*.dump"))
    runtime.cleanup_stale()
    assert runtime.maintenance()
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"email": "h3@example.com", "password": inst["password"]}).status_code == 503
        assert client.patch("/api/system-settings/auth.session_minutes", json={"value": 22}).status_code == 503
        assert client.get("/api/health").json()["status"] == "maintenance"
    inst["monkeypatch"].setattr(service.postgres, "replace", original_replace)
    service.rollback(marker["job_id"])
    assert runtime.maintenance() is None


def test_rewrap_all_adapters_active_pending_atomic_wrong_key_and_corrupt(installations):
    inst = installations
    assert len(ENCRYPTED_DATA_ADAPTERS) == 2
    with Session(inst["source"]) as db:
        original = db.get(UserMfa, inst["ids"]["user"]).secret_ciphertext
        with pytest.raises(BackupError):
            rewrap_application_data(db, secrets.token_bytes(32), bytes.fromhex(inst["target_key"]))
        db.rollback()
        assert db.get(UserMfa, inst["ids"]["user"]).secret_ciphertext == original
        assert rewrap_application_data(db, bytes.fromhex(inst["source_key"]), bytes.fromhex(inst["target_key"])) == 2
        db.commit()
        inst["monkeypatch"].setenv("ATLAS_DATA_ENCRYPTION_KEY", inst["target_key"])
        state = db.get(UserMfa, inst["ids"]["user"])
        assert state.secret_ciphertext != original
        assert mfa.decrypt_seed(state.user_id, state.secret_nonce, state.secret_ciphertext) == inst["seed"]
        assert mfa.decrypt_seed(state.user_id, state.pending_nonce, state.pending_ciphertext) == inst["seed"]
        pending = state.pending_ciphertext
        state.pending_ciphertext = b"corrupt"
        db.commit()
        before = state.secret_ciphertext
        with pytest.raises(BackupError):
            rewrap_application_data(db, bytes.fromhex(inst["target_key"]), secrets.token_bytes(32))
        db.rollback()
        assert db.get(UserMfa, state.user_id).secret_ciphertext == before


def test_backup_api_authorization_reauth_no_secret_echo_job_download_idor(installations):
    inst = installations
    inst["monkeypatch"].setattr(backups, "_jobs", backups.BackupJobs(inst["source"]))
    def database():
        with Session(inst["source"], autoflush=False, expire_on_commit=False) as db:
            yield db
    app.dependency_overrides[get_db] = database
    token = create_session_token(inst["ids"]["user"], 1)
    payload = {"passphrase": inst["passphrase"], "passphrase_confirmation": inst["passphrase"], "current_password": inst["password"]}
    with TestClient(app) as client:
        assert client.post("/api/system-settings/backups", json=payload).status_code == 401
        client.cookies.set(COOKIE_NAME, token)
        assert client.post("/api/system-settings/backups", json={**payload, "unexpected": inst["passphrase"]}).status_code == 422
        wrong = client.post("/api/system-settings/backups", json={**payload, "current_password": secrets.token_urlsafe(24)})
        assert wrong.status_code == 400
        response = client.post("/api/system-settings/backups", json=payload)
        assert response.status_code == 202
        job_id = response.json()["id"]
        for _ in range(300):
            result = client.get(f"/api/system-settings/backups/{job_id}").json()
            if result["state"] not in {"preparing", "requested"}: break
            time.sleep(.05)
        assert result["state"] == "ready", result["message"]
        with Session(inst["source"]) as db:
            user = User(email="other@example.com", display_name="Other master", password_hash=hash_password(secrets.token_urlsafe(24)))
            db.add(user); db.flush()
            role = db.scalar(select(Role).where(Role.name == "Master Administrator"))
            db.add(AccessAssignment(user_id=user.id, role_id=role.id, scope_type="global")); db.commit()
            other_token = create_session_token(user)
        client.cookies.set(COOKIE_NAME, other_token)
        assert client.get(f"/api/system-settings/backups/{job_id}/download").status_code == 404
        client.cookies.set(COOKIE_NAME, token)
        download = client.get(f"/api/system-settings/backups/{job_id}/download")
        assert download.status_code == 200 and download.content[:8] == b"ATLASBKP"
        assert download.headers["cache-control"] == "no-store"
        assert ".atlasbackup" in download.headers["content-disposition"]
        assert client.get(f"/api/system-settings/backups/{job_id}/download").status_code == 410
        assert not list(runtime.state_directory().glob("*/*.atlasbackup"))
        missing_factor = client.post("/api/system-settings/restore/authorize", json={"current_password": inst["password"], "passphrase": inst["passphrase"], "acknowledgement": "RESTORE"})
        assert missing_factor.status_code == 400
        wrong_origin = client.post("/api/system-settings/backups", json=payload, headers={"Origin": "https://foreign.example"})
        assert wrong_origin.status_code == 403
    with Session(inst["source"]) as db:
        metadata = json.dumps(list(db.scalars(select(AuditEvent.metadata_))))
        assert inst["passphrase"] not in metadata and inst["source_key"] not in metadata


def test_h1_schema_restores_and_migrates_forward_without_stale_new_tables(installations):
    inst = installations
    config = migration_config()
    with inst["source"].begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "20261004_0025")
    archive = portable_backup(inst)
    restore(inst, archive)
    with inst["target"].connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261012_0028"
    with Session(inst["target"]) as db:
        assert db.get(User, inst["ids"]["user"]).mfa_enabled is False
        assert db.get(Asset, inst["ids"]["asset"]).name == "Portable host"


@pytest.mark.parametrize("scope", ["customer", "custom_global"])
def test_export_restore_deny_scoped_and_custom_global_administrators(installations, scope):
    inst = installations
    with Session(inst["source"]) as db:
        assignment = db.scalar(select(AccessAssignment))
        if scope == "customer":
            assignment.customer_id = db.scalar(select(Customer.id))
            assignment.scope_type = "customer"
        else:
            from app.models import Permission, RolePermission
            role = Role(name="Custom settings administrator", active=True)
            db.add(role); db.flush()
            permission = db.scalar(select(Permission).where(Permission.key == "system_settings.manage"))
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
            assignment.role_id = role.id
        db.commit()
    def database():
        with Session(inst["source"]) as db:
            yield db
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        client.cookies.set(COOKIE_NAME, create_session_token(inst["ids"]["user"], 1))
        payload = {"current_password": inst["password"], "passphrase": inst["passphrase"], "passphrase_confirmation": inst["passphrase"]}
        assert client.post("/api/system-settings/backups", json=payload).status_code == 403
        assert client.post("/api/system-settings/restore/authorize", json={"current_password": inst["password"], "passphrase": inst["passphrase"], "acknowledgement": "RESTORE"}).status_code == 403
    assert not list(runtime.state_directory().glob("*/status.json"))


def test_fresh_setup_authorization_upload_preflight_and_scoped_status(installations):
    inst = installations
    archive = portable_backup(inst)
    inst["monkeypatch"].setenv("ATLAS_DATA_ENCRYPTION_KEY", inst["target_key"])
    def database():
        with Session(inst["target"], autoflush=False, expire_on_commit=False) as db:
            yield db
    app.dependency_overrides[get_db] = database
    payload = {"passphrase": inst["passphrase"]}
    with TestClient(app) as client:
        assert client.post("/api/setup/restore/authorize", json=payload).status_code == 401
        with Session(inst["target"]) as db:
            code = reset_setup_code(db); db.commit()
        assert client.post("/api/setup/verify", json={"code": code}).status_code == 204
        response = client.post("/api/setup/restore/authorize", json=payload)
        assert response.status_code == 202
        job_id = response.json()["id"]
        cookie = client.cookies["atlas_restore_status"]
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "/api/restore-status" in response.headers["set-cookie"]
        assert client.get(f"/api/restore-status/{uuid.uuid4()}").status_code == 404
        # Missing setup authorization cannot use even a known restore job ID.
        client.cookies.delete(SETUP_COOKIE)
        assert client.put(f"/api/setup/restore/{job_id}/upload", content=archive.read_bytes()).status_code == 401
        assert client.post("/api/setup/verify", json={"code": code}).status_code == 204
        upload = client.put(f"/api/setup/restore/{job_id}/upload", content=archive.read_bytes(), headers={"Content-Type": "application/octet-stream"})
        assert upload.status_code == 202
        for _ in range(300):
            status = client.get(f"/api/restore-status/{job_id}").json()
            if status["state"] in {"failed", "complete"}: break
            time.sleep(.05)
        assert status["state"] == "complete", status["message"]
        assert client.get("/api/setup/status").json()["state"] == "INITIALISED"
        assert client.post("/api/setup/verify", json={"code": code}).status_code == 409
        assert client.post("/api/setup/restore/authorize", json=payload).status_code == 409
        client.cookies.delete("atlas_restore_status")
        assert client.get(f"/api/restore-status/{job_id}").status_code == 404
        assert not list(runtime.state_directory().glob("*/*.dump"))


def test_local_backup_recovery_from_damaged_database_stays_closed_until_validated(installations):
    inst = installations
    archive = portable_backup(inst)
    inst["monkeypatch"].setenv("ATLAS_DATA_ENCRYPTION_KEY", inst["target_key"])
    jobs = inst["jobs"]
    job_id, fd, _ = jobs.reserve(kind="restore", owner="local-operator", actor_email="local-operator", mode="local")
    work = runtime.job_directory(job_id)
    shutil.copyfile(archive, work / "upload.atlasbackup")
    with inst["target"].begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE")); connection.execute(text("CREATE SCHEMA public"))
    runtime.set_maintenance(job_id, "recovery_required")
    try:
        with pytest.raises(BackupError):
            jobs.service.restore(job_id, secrets.token_urlsafe(24), {"mode": "local", "actor_email": "local-operator"}, recovery=True)
        assert runtime.maintenance()
        jobs.service.restore(job_id, inst["passphrase"], {"mode": "local", "actor_email": "local-operator"}, recovery=True)
        assert runtime.maintenance() is None
        with Session(inst["target"]) as db:
            assert db.get(Asset, inst["ids"]["asset"]).name == "Portable host"
    finally:
        runtime.unlock(fd)


def test_actual_local_cli_create_restore_and_protected_output(installations):
    inst = installations
    output = inst["tmp"] / "operator.atlasbackup"
    environment = {**os.environ, "DATABASE_URL": os.environ["ATLAS_TEST_H3_SOURCE_URL"],
                   "ATLAS_DATA_ENCRYPTION_KEY": inst["source_key"]}
    result = subprocess.run([sys.executable, "-m", "scripts.backup", "create", "--output", str(output)],
                            input=inst["passphrase"] + "\n" + inst["passphrase"] + "\n",
                            env=environment, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, "Local CLI creation failed"
    assert output.stat().st_mode & 0o777 == 0o600
    assert inst["passphrase"] not in result.stdout + result.stderr
    environment.update(DATABASE_URL=os.environ["ATLAS_TEST_H3_TARGET_URL"], ATLAS_DATA_ENCRYPTION_KEY=inst["target_key"])
    result = subprocess.run([sys.executable, "-m", "scripts.backup", "restore", "--input", str(output)],
                            input="RESTORE\n" + inst["passphrase"] + "\n", env=environment,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, "Local CLI restoration failed"
    assert inst["passphrase"] not in result.stdout + result.stderr
    with Session(inst["target"]) as db:
        assert db.get(Asset, inst["ids"]["asset"]).name == "Portable host"
    assert runtime.maintenance() is None


def test_maintenance_blocks_application_auth_setup_and_new_jobs_but_allows_scoped_progress(installations):
    inst = installations
    jobs = inst["jobs"]
    job_id, fd, token = jobs.reserve(kind="restore", owner="local-operator", actor_email="local-operator", mode="local")
    runtime.set_maintenance(job_id, "replacing")
    try:
        with TestClient(app) as client:
            assert client.get("/api/health").json() == {"status": "maintenance"}
            for method, path in [("GET", "/api/assets"), ("POST", "/api/assets"),
                                 ("POST", "/api/auth/login"), ("POST", "/api/setup/verify"),
                                 ("POST", "/api/system-settings/backups")]:
                response = client.request(method, path, json={})
                assert response.status_code == 503
                assert response.headers["cache-control"] == "no-store"
            assert client.get(f"/api/restore-status/{job_id}").status_code == 404
            client.cookies.set("atlas_restore_status", token)
            assert client.get(f"/api/restore-status/{job_id}").status_code == 200
            with pytest.raises(BackupError):
                jobs.reserve(kind="restore", owner="other", actor_email="other")
    finally:
        runtime.clear_maintenance()
        runtime.unlock(fd)
