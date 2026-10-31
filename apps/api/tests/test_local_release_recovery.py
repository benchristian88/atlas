"""Final review recovery regressions; real root files, signatures and PostgreSQL."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
import secrets
import time

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import AuditEvent, InstalledConnectorPackage, Integration, IntegrationSecret, SystemSetting
from app.routes import integration_connections as connections
from app.services import connector_lifecycle as lifecycle, connector_release_acceptance as service
from app.services import local_release_authority as authority
from app.services import local_release_restoration as restoration
from app.services.connector_catalogue import catalogue
from app.services.connector_store import PackageStore
from app.services.integration_connections import installed_manifest
from tests.test_local_release_authority_postgres import db, configured, unenrolled, staged, runtime, pytestmark
from tests.test_local_release_remediation import activate, fresh_admission, maintenance_plan
from tests.test_connector_release_acceptance import public_responses, IDENTITY
from tests.test_administration import request
from tests.test_administration import make_principal


def test_clear_expire_repair_review_renew_and_manual_execution(db, staged, configured, monkeypatch):
    active = activate(db, staged)
    row, principal = staged[3], configured[1]
    context = authority.execution_context(active)
    connections.clear_credentials(row.id, connections.Confirm(confirmed=True), request(), principal, db)
    epoch = context["activation"]["expires_at"] + 1
    monkeypatch.setattr(time, "time", lambda: epoch)
    assert fresh_admission(staged, context, epoch=epoch) == "denied"
    with pytest.raises(HTTPException) as denied:
        asyncio.run(connections.test_connection(row.id, request(), principal, db))
    assert denied.value.status_code == 409
    with pytest.raises(ValueError, match="execution_denied"):
        installed_manifest(db, "proxmox")
    values = {"token_id": secrets.token_hex(12), "token_secret": secrets.token_hex(24)}
    result = connections.replace_credentials(row.id, connections.Credentials(values=values), request(), principal, db)
    assert result["credential_configured"]
    connections.update_integration(row.id, connections.ConnectionUpdate(config={**row.config_json, "tls_policy": "verify"}),
                                   request(), principal, db)
    assert authority.execution_context(active) == context
    assert fresh_admission(staged, context, epoch=epoch) == "denied"
    plan, isolation = maintenance_plan(db, staged, "renew")
    renewed = asyncio.run(service.maintain_execution(db, staged[0].root, IDENTITY, plan["approval_digest"],
        runtime(staged), action="renew", isolation=isolation))
    assert fresh_admission(staged, authority.execution_context(renewed), epoch=epoch) == "authorized"
    assert installed_manifest(db, "proxmox")[0].version == IDENTITY.version
    from app.services.discovery_orchestration import create_run
    run = asyncio.run(create_run(db, row, trigger="manual", user_id=principal.user.id))
    assert run.execution_provenance["local_execution"] == authority.execution_context(renewed)


def handoff(db, staged, tmp_path):
    context = deepcopy(authority.execution_context(activate(db, staged)))
    service.revoke(staged[0].root, staged[1].verification["authorization_id"], db=db)
    target = PackageStore(tmp_path / "bundled-store")
    package = catalogue.get("proxmox", "0.1.0")
    target.install(package, catalogue.verifier())
    plan = restoration.plan(db, staged[0].root, target.root, "proxmox", package.version, package.bundle_digest[7:], scopes=[])
    proof = restoration.authorize(db, staged[0].root, target.root, "proxmox", package.version,
                          package.bundle_digest[7:], plan["plan_digest"], scopes=[])
    return target, package, proof, context


def route_harness(db, target, health, monkeypatch):
    from atlas_runtime.server import Runtime
    from app.routes import integrations as routes
    monkeypatch.setattr(lifecycle, "package_store", lambda: PackageStore(target.root))
    real = Runtime(secrets.token_hex(48), target.root, "development")
    async def healthy(): return deepcopy(health)
    async def verify(reference): return real.verify_connector(reference)
    monkeypatch.setattr(routes.runtime, "health", healthy)
    monkeypatch.setattr(routes.runtime, "verify_connector", verify)
    principal = make_principal("integration_runtime.manage", "integration_runtime.view")
    db.add(principal.user); db.commit()
    return real, principal


def test_revoked_local_can_return_to_separate_bundled_store(db, staged, monkeypatch, tmp_path):
    from sqlalchemy.orm import Session
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    from app.authorization import get_principal
    from tests.test_connector_lifecycle_api import retained_history, assert_history_preserved
    row = staged[3]
    before = (row.config_json, row.credential_reference, row.data_source_id, row.customer_id, row.site_id)
    encrypted = deepcopy(service.snapshot(db.get(IntegrationSecret, row.credential_reference)))
    history = retained_history(db)
    target, package, proof, context = handoff(db, staged, tmp_path)
    real, principal = route_harness(db, target, staged[4], monkeypatch)
    # Simulate an API process restart: new Session, no pending operator state.
    db.rollback()
    try:
        with Session(db.get_bind(), expire_on_commit=False) as restarted:
            app.dependency_overrides[get_db] = lambda: restarted
            app.dependency_overrides[get_principal] = lambda: principal
            result = TestClient(app).post("/api/integration-catalogue/proxmox/activate",
                json={"version": package.version, "digest": package.bundle_digest[7:]})
            assert result.status_code == 200, result.text
        with Session(db.get_bind()) as independent:
            active = independent.get(InstalledConnectorPackage, "proxmox")
            row = independent.get(Integration, row.id)
            assert active.version == "0.1.0" and active.verification_evidence["method"] == "atlas-release-bootstrap"
            assert (row.config_json, row.credential_reference, row.data_source_id, row.customer_id, row.site_id) == before
            assert service.snapshot(independent.get(IntegrationSecret, row.credential_reference)) == encrypted
            assert_history_preserved(independent, history)
            assert row.selected_scopes == [] and proof["previous_scopes"][0]["selected_scopes"] == ["inventory"]
            assert independent.scalar(select(SystemSetting).where(SystemSetting.key == restoration.PREFIX + "proxmox")) is None
            assert independent.scalar(select(AuditEvent.id).where(AuditEvent.event_type == "connector.local_restoration_completed"))
            assert installed_manifest(independent, "proxmox")[0].version == "0.1.0"
        assert fresh_admission(staged, context) == "denied"
        real.execution_admission({"connector_id": "proxmox", "version": package.version,
            "digest": package.bundle_digest[7:]}, None)
    finally:
        app.dependency_overrides.clear()
        real.jobs.shutdown()


def test_interrupted_revocation_does_not_publish_partial_final_evidence(db, staged, monkeypatch):
    active = activate(db, staged)
    identifier = staged[1].verification["authorization_id"]
    final = staged[0].root / authority.DIRECTORY / (identifier + ".revoked.json")
    original = os.fsync
    def interrupted(descriptor):
        import stat
        if stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("injected data synchronization interruption")
        return original(descriptor)
    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", interrupted)
        with pytest.raises((OSError, ValueError)):
            service.revoke(staged[0].root, identifier, db=db)
    assert not final.exists(), "interrupted write exposed unauthenticatable final tombstone"
    assert fresh_admission(staged, authority.execution_context(active)) == "denied"
    assert service.revoke(staged[0].root, identifier, db=db)["audit"] == "recorded"
    assert service.reconcile_revocation(staged[0].root, identifier, db=db)["audit"] == "recorded"
    assert len(list(db.scalars(select(AuditEvent).where(AuditEvent.event_type == "connector.local_release_revoked")))) == 1


@pytest.mark.parametrize("failure", ["no_handoff", "wrong_store", "altered_signature", "altered_revocation",
    "stale_active", "stale_dependents", "wrong_package", "tampered_package"])
def test_restoration_denies_switches_tampering_and_stale_state(db, staged, monkeypatch, tmp_path, failure):
    target, package, proof, context = handoff(db, staged, tmp_path)
    stored = target.install(package, catalogue.verifier())
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == restoration.PREFIX + "proxmox"))
    if failure == "no_handoff": db.delete(setting)
    elif failure == "wrong_store":
        target = PackageStore(tmp_path / "other-bundled-store")
        stored = target.install(package, catalogue.verifier())
    elif failure == "altered_signature":
        setting.value_ = {**setting.value_, "signature": "AAAA"}
    elif failure == "altered_revocation":
        path = staged[0].root / authority.DIRECTORY / (staged[1].verification["authorization_id"] + ".revoked.json")
        value = json.loads(path.read_bytes()); value["payload"]["artifact_id"] = "changed"
        path.chmod(0o644); path.write_bytes(authority.canonical(value)); path.chmod(0o444)
    elif failure == "stale_active":
        db.get(InstalledConnectorPackage, "proxmox").verification_evidence = {
            **db.get(InstalledConnectorPackage, "proxmox").verification_evidence, "local_activation": {"generation": "changed"}}
    elif failure == "stale_dependents": staged[3].name = "Changed after operator authorization"
    elif failure == "wrong_package": stored = replace(stored, verification={**stored.verification, "release_identity": "changed"})
    elif failure == "tampered_package":
        path = target._path(package.connector_id, package.version, package.bundle_digest) / "contents/NOTICE"
        path.chmod(0o644); path.write_text("changed")
    db.commit()
    monkeypatch.setattr(lifecycle, "package_store", lambda: target)
    with pytest.raises((ValueError, OSError)):
        lifecycle.activate(db, stored, staged[4])
    db.rollback()
    assert db.get(InstalledConnectorPackage, "proxmox").version == IDENTITY.version
    assert fresh_admission(staged, context) == "denied"


@pytest.mark.parametrize("failure", ["missing_revocation", "wrong_original_store", "incompatible_scopes", "nonroot"])
def test_restoration_authorization_fails_closed(db, staged, tmp_path, monkeypatch, failure):
    activate(db, staged)
    if failure != "missing_revocation":
        service.revoke(staged[0].root, staged[1].verification["authorization_id"], db=db)
    original = staged[0].root if failure != "wrong_original_store" else tmp_path / "wrong-original"
    target = PackageStore(tmp_path / "bundled-store")
    package = catalogue.get("proxmox", "0.1.0")
    target.install(package, catalogue.verifier())
    if failure == "nonroot": monkeypatch.setattr(authority.os, "geteuid", lambda: 10001)
    with pytest.raises((ValueError, OSError)):
        restoration.plan(db, original, target.root, "proxmox", package.version, package.bundle_digest[7:],
                         scopes=None if failure == "incompatible_scopes" else [])
    db.rollback()
    assert db.get(InstalledConnectorPackage, "proxmox").version == IDENTITY.version


def test_restoration_commit_failure_keeps_handoff_and_original_activation(db, staged, monkeypatch, tmp_path):
    from app.routes import integrations as routes
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    target, package, proof, context = handoff(db, staged, tmp_path)
    real, principal = route_harness(db, target, staged[4], monkeypatch)
    try:
        def failed(): raise SQLAlchemyError("injected transaction failure")
        with monkeypatch.context() as patch:
            patch.setattr(db, "commit", failed)
            with pytest.raises(HTTPException):
                asyncio.run(routes._install("proxmox", routes.PackageSelection(version=package.version,
                    digest=package.bundle_digest[7:]), request(), principal, db))
        with Session(db.get_bind()) as independent:
            assert independent.get(InstalledConnectorPackage, "proxmox").version == IDENTITY.version
            assert independent.get(Integration, staged[3].id).selected_scopes == ["inventory"]
            assert independent.scalar(select(SystemSetting).where(SystemSetting.key == restoration.PREFIX + "proxmox"))
            assert not independent.scalar(select(AuditEvent.id).where(AuditEvent.event_type == "connector.local_restoration_completed"))
        # Retry the same persisted handoff after a rolled-back transaction.
        assert asyncio.run(routes._install("proxmox", routes.PackageSelection(version=package.version,
            digest=package.bundle_digest[7:]), request(), principal, db))["version"] == package.version
        assert fresh_admission(staged, context) == "denied"
    finally:
        real.jobs.shutdown()


def test_consumed_handoff_cannot_be_replayed_after_new_local_generation(db, staged, monkeypatch, tmp_path):
    target, package, proof, context = handoff(db, staged, tmp_path)
    saved = deepcopy(db.scalar(select(SystemSetting).where(SystemSetting.key == restoration.PREFIX + "proxmox")).value_)
    original_active = deepcopy(service.snapshot(db.get(InstalledConnectorPackage, "proxmox")))
    stored = target.install(package, catalogue.verifier())
    monkeypatch.setattr(lifecycle, "package_store", lambda: target)
    lifecycle.activate(db, stored, staged[4]); db.commit()
    assert db.scalar(select(SystemSetting).where(SystemSetting.key == restoration.PREFIX + "proxmox")) is None
    # Replay the old signed proof against a different activation. No signature
    # or privileged filesystem protection is mocked to let the replay pass.
    active = db.get(InstalledConnectorPackage, "proxmox")
    for key, value in original_active.items(): setattr(active, key, value)
    active.verification_evidence = {**active.verification_evidence,
        "local_activation": {**active.verification_evidence["local_activation"], "generation": "new-generation"}}
    db.add(SystemSetting(key=restoration.PREFIX + "proxmox", value_=saved, sensitive=True)); db.commit()
    with pytest.raises(ValueError, match="handoff_mismatch"):
        lifecycle.activate(db, stored, staged[4])
    db.rollback()
    assert fresh_admission(staged, context) == "denied"


@pytest.mark.parametrize("failure", ["other_tenant", "schema", "integrity"])
def test_expired_maintenance_retains_scope_schema_and_integrity(db, staged, configured, monkeypatch, failure):
    active = activate(db, staged)
    epoch = active.verification_evidence["local_activation"]["expires_at"] + 1
    monkeypatch.setattr(time, "time", lambda: epoch)
    principal = configured[1]
    if failure == "other_tenant":
        import uuid
        principal = replace(principal, grants=tuple(replace(g, scope_type="site", customer_id=uuid.uuid4(), site_id=uuid.uuid4())
            for g in principal.grants))
    if failure == "integrity":
        path = staged[0]._path(IDENTITY.connector_id, IDENTITY.version, "sha256:" + IDENTITY.sha256) / "contents/NOTICE"
        path.chmod(0o644); path.write_text("tampered")
    values = {"token_id": secrets.token_hex(12), "token_secret": secrets.token_hex(24)} if failure != "schema" else {"undeclared": "invalid"}
    with pytest.raises(HTTPException) as rejected:
        connections.replace_credentials(staged[3].id, connections.Credentials(values=values), request(), principal, db)
    assert rejected.value.status_code == (404 if failure == "other_tenant" else 409)


@pytest.mark.parametrize("phase", ["write", "publication", "directory_sync"])
def test_revocation_faults_remain_denied_and_retryable(db, staged, monkeypatch, phase):
    from app.services import local_release_revocation as revocation
    active = activate(db, staged)
    identifier = staged[1].verification["authorization_id"]
    final, pending = revocation.paths(staged[0].root, identifier)
    with monkeypatch.context() as patch:
        if phase == "write":
            original = os.fdopen
            class Interrupted:
                def __init__(self, stream): self.stream = stream
                def __enter__(self): return self
                def __exit__(self, *args): self.stream.close()
                def write(self, raw):
                    self.stream.write(raw[:10]); self.stream.flush()
                    raise OSError("injected partial temporary write")
            def opening(descriptor, mode, *args, **kwargs):
                stream = original(descriptor, mode, *args, **kwargs)
                return Interrupted(stream) if mode == "wb" else stream
            patch.setattr(os, "fdopen", opening)
        elif phase == "publication":
            def failed(*args, **kwargs): raise OSError("injected link failure")
            patch.setattr(os, "link", failed)
        else:
            original = authority.sync_directory
            def failed(path):
                if final.exists(): raise OSError("injected post-publication directory sync failure")
                original(path)
            patch.setattr(authority, "sync_directory", failed)
        with pytest.raises((ValueError, OSError)):
            service.revoke(staged[0].root, identifier, db=db)
    assert pending.exists()
    if final.exists(): revocation.verified(staged[0].root, identifier, staged[2])
    assert fresh_admission(staged, authority.execution_context(active)) == "denied"
    assert service.revoke(staged[0].root, identifier, db=db)["audit"] == "recorded"


def test_revocation_process_crash_and_fresh_process_retry(db, staged):
    import subprocess
    import sys
    from app.services import local_release_revocation as revocation
    context = authority.execution_context(activate(db, staged))
    identifier = staged[1].verification["authorization_id"]
    child = '''import json,os,sys,stat
from pathlib import Path
from app.services import local_release_authority as a,local_release_revocation as r
p=json.load(sys.stdin)
a.BINDING=Path(p['binding']);a.DEPLOYMENT=Path(p['deployment']);a.PRIVATE_KEY=Path(p['private'])
original=os.fsync
def crash(fd):
 if stat.S_ISREG(os.fstat(fd).st_mode):os._exit(37)
 original(fd)
os.fsync=crash
r.publish(Path(p['store']),p['identifier'])
'''
    result = subprocess.run([sys.executable, "-c", child], input=json.dumps({"binding": str(authority.BINDING),
        "deployment": str(authority.DEPLOYMENT), "private": str(authority.PRIVATE_KEY),
        "store": str(staged[0].root), "identifier": identifier}).encode(), capture_output=True, timeout=20)
    assert result.returncode == 37, result.stderr.decode()
    final, pending = revocation.paths(staged[0].root, identifier)
    assert pending.exists() and not final.exists()
    assert list(final.parent.glob("*.revocation-tmp"))
    assert fresh_admission(staged, context) == "denied"
    assert service.revoke(staged[0].root, identifier, db=db)["audit"] == "recorded"
    assert service.revoke(staged[0].root, identifier, db=db)["audit"] == "recorded"
    with pytest.raises(ValueError, match="revoked"): maintenance_plan(db, staged, "recover")


@pytest.mark.parametrize("raw", [b'{"payload":', b'corrupt evidence', b''])
def test_corrupt_tombstone_explicit_root_recovery_retains_evidence_and_audit(db, staged, monkeypatch, raw):
    from app import database
    context = authority.execution_context(activate(db, staged))
    identifier = staged[1].verification["authorization_id"]
    final = staged[0].root / authority.DIRECTORY / (identifier + ".revoked.json")
    # Historical interrupted publisher created a writable partial final file.
    final.write_bytes(raw)
    assert fresh_admission(staged, context) == "denied"
    with pytest.raises(ValueError, match="recovery_required"):
        service.revoke(staged[0].root, identifier, db=db)
    with pytest.raises(ValueError, match="evidence_changed"):
        service.revoke(staged[0].root, identifier, db=db, corrupt_sha256="0" * 64)
    with monkeypatch.context() as patch:
        patch.setattr(authority.os, "geteuid", lambda: 10001)
        with pytest.raises(ValueError, match="root_operator"):
            service.revoke(staged[0].root, identifier, db=db, corrupt_sha256=hashlib.sha256(raw).hexdigest())
    def unavailable(): raise OSError("disposable database unavailable")
    with monkeypatch.context() as patch:
        patch.setattr(database, "SessionLocal", unavailable)
        assert service.revoke(staged[0].root, identifier, corrupt_sha256=hashlib.sha256(raw).hexdigest())["audit"] == "reconciliation_required"
    retained = list(final.parent.glob(identifier + ".*.corrupt-evidence"))
    assert len(retained) == 1 and retained[0].read_bytes() == raw
    assert retained[0].stat().st_mode & 0o777 == 0o444
    for _ in range(2):
        assert service.reconcile_revocation(staged[0].root, identifier, db=db)["audit"] == "recorded"
        assert service.revoke(staged[0].root, identifier, db=db)["audit"] == "recorded"
    for event in ("connector.local_release_revoked", "connector.local_revocation_recovered"):
        assert len(list(db.scalars(select(AuditEvent).where(AuditEvent.event_type == event)))) == 1
    assert fresh_admission(staged, context) == "denied"


def test_handoff_still_requires_normal_global_install_permission(db, staged, monkeypatch, tmp_path):
    from app.routes import integrations as routes
    target, package, proof, _ = handoff(db, staged, tmp_path)
    real, principal = route_harness(db, target, staged[4], monkeypatch)
    restricted = replace(principal, grants=tuple(replace(g, scope_type="site", customer_id=staged[3].customer_id,
        site_id=staged[3].site_id) for g in principal.grants))
    try:
        with pytest.raises(HTTPException) as denied:
            asyncio.run(routes._install("proxmox", routes.PackageSelection(version=package.version,
                digest=package.bundle_digest[7:]), request(), restricted, db))
        assert denied.value.status_code == 403
        assert db.scalar(select(SystemSetting).where(SystemSetting.key == restoration.PREFIX + "proxmox"))
    finally:
        real.jobs.shutdown()


def test_restoration_refuses_active_runs_and_stale_review(db, staged, tmp_path):
    from app.services.discovery_orchestration import create_run
    from app.models import DiscoveryRun
    activate(db, staged)
    run = asyncio.run(create_run(db, staged[3], trigger="manual"))
    db.commit()
    service.revoke(staged[0].root, staged[1].verification["authorization_id"], db=db)
    target = PackageStore(tmp_path / "bundled-store")
    package = catalogue.get("proxmox", "0.1.0")
    target.install(package, catalogue.verifier())
    with pytest.raises(ValueError, match="active_runs"):
        restoration.plan(db, staged[0].root, target.root, "proxmox", package.version, package.bundle_digest[7:], scopes=[])
    db.rollback()
    run = db.get(DiscoveryRun, run.id)
    run.status = "cancelled"; run.dispatch_state = "settled"; db.commit()
    plan = restoration.plan(db, staged[0].root, target.root, "proxmox", package.version, package.bundle_digest[7:], scopes=[])
    staged[3].name = "Dependency changed after review"; db.commit()
    with pytest.raises(ValueError, match="stale_restoration_plan"):
        restoration.authorize(db, staged[0].root, target.root, "proxmox", package.version,
                              package.bundle_digest[7:], plan["plan_digest"], scopes=[])


def test_concurrent_revocations_keep_one_authenticated_tombstone(db, staged):
    from concurrent.futures import ThreadPoolExecutor
    from app.services import local_release_revocation as revocation
    context = authority.execution_context(activate(db, staged))
    identifier = staged[1].verification["authorization_id"]
    def publish():
        try:
            revocation.publish(staged[0].root, identifier)
            return "revoked"
        except ValueError as error:
            assert str(error) == "package_operation_in_progress"
            return "retry"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(), range(2)))
    assert "revoked" in results
    path, _ = revocation.paths(staged[0].root, identifier)
    before = path.read_bytes()
    for _ in range(2): service.revoke(staged[0].root, identifier, db=db)
    assert path.read_bytes() == before
    revocation.verified(staged[0].root, identifier, staged[2])
    assert fresh_admission(staged, context) == "denied"
    assert len(list(db.scalars(select(AuditEvent).where(AuditEvent.event_type == "connector.local_release_revoked")))) == 1


def test_application_cannot_alter_pending_handoff(db, staged, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    from app.authorization import get_principal
    target, package, proof, _ = handoff(db, staged, tmp_path)
    principal = make_principal("system_settings.manage")
    db.add(principal.user); db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        result = TestClient(app).patch("/api/system-settings/" + restoration.PREFIX + "proxmox", json={"value": {}})
        assert result.status_code == 409
    finally:
        app.dependency_overrides.clear()
    assert db.scalar(select(SystemSetting).where(SystemSetting.key == restoration.PREFIX + "proxmox")).value_["payload"] == proof


def test_operator_cli_handoff_and_activation_survive_real_process_restarts(db, staged, tmp_path):
    import subprocess
    import sys
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    activate(db, staged)
    service.revoke(staged[0].root, staged[1].verification["authorization_id"], db=db)
    target = PackageStore(tmp_path / "bundled-store")
    package = catalogue.get("proxmox", "0.1.0")
    target.install(package, catalogue.verifier())
    # Emulate public read-only consumer mounts while preserving the real 0700
    # private-key and retained release-evidence directories.
    for parent in (tmp_path, *tmp_path.parents):
        if str(parent) == "/tmp": break
        parent.chmod(0o755)
    schema = db.scalar(text("SELECT current_schema()")); db.rollback()
    env = dict(os.environ)
    env['DATABASE_URL'] = db.get_bind().url.update_query_dict({"options": "-csearch_path=" + schema}).render_as_string(hide_password=False)
    payload = {"binding": str(authority.BINDING), "private": str(authority.PRIVATE_KEY), "deployment": str(authority.DEPLOYMENT),
        "original": str(staged[0].root), "target": str(target.root), "version": package.version,
        "digest": package.bundle_digest[7:], "health": staged[4]}
    child = '''import asyncio,json,os,sys
from pathlib import Path
from app.services import local_release_authority as a,connector_lifecycle as lifecycle
p=json.load(sys.stdin)
a.BINDING=Path(p['binding']);a.PRIVATE_KEY=Path(p['private']);a.DEPLOYMENT=Path(p['deployment'])
if p['action']!='activate':
 os.environ['ATLAS_CONNECTOR_STORE_PATH']=p['original']
 sys.argv=['accept_connector_release',p['action'],'--connector-id','proxmox','--version',p['version'],'--sha256',p['digest'],
  '--replacement-store',p['target'],'--clear-scopes']
 if p.get('approved'):sys.argv+=['--approve-plan',p['approved']]
 from scripts.accept_connector_release import main
 main()
else:
 os.environ['ATLAS_CONNECTOR_STORE_PATH']=p['target']
 os.setgroups([]);os.setgid(10001);os.setuid(10001)
 try:Path(p['private']).read_bytes();raise AssertionError('application read operator private key')
 except PermissionError:pass
 try:list((Path(p['original'])/'.local-acceptance'/p['authorization_id']).iterdir());raise AssertionError('application read root release evidence')
 except PermissionError:pass
 from app.database import SessionLocal
 from app.routes import integrations as routes
 from atlas_runtime.server import Runtime
 from tests.test_administration import make_principal,request
 real=Runtime('restart-test-control',Path(p['target']),'development')
 async def health():return p['health']
 async def verify(ref):return real.verify_connector(ref)
 routes.runtime.health=health;routes.runtime.verify_connector=verify
 try:
  with SessionLocal() as db:
   principal=make_principal('integration_runtime.manage');db.add(principal.user);db.commit()
   result=asyncio.run(routes._install('proxmox',routes.PackageSelection(version=p['version'],digest=p['digest']),request(),principal,db))
   print(json.dumps(result,default=str))
 finally:real.jobs.shutdown()
'''
    def call(action, **extra):
        result = subprocess.run([sys.executable, "-c", child], input=json.dumps({**payload, "action": action,
            "authorization_id": staged[1].verification["authorization_id"], **extra}).encode(),
            env=env, capture_output=True, timeout=30, check=True)
        return json.loads(result.stdout)
    plan = call("plan-restoration")
    proof = call("authorize-restoration", approved=plan["plan_digest"])
    assert call("activate")["version"] == package.version
    with Session(db.get_bind()) as independent:
        assert independent.get(InstalledConnectorPackage, "proxmox").verification_evidence["method"] == "atlas-release-bootstrap"
        assert independent.scalar(select(AuditEvent.id).where(AuditEvent.event_type == "connector.local_restoration_completed",
            AuditEvent.metadata_["transition_id"].astext == proof["transition_id"]))
