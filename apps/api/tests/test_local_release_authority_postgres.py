"""Root-owned files, real signatures, real PostgreSQL; no source execution."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import shutil
import time

import pytest
from sqlalchemy import select, create_engine, text
from sqlalchemy.orm import Session

from app.models import InstalledConnectorPackage, SystemSetting, AssetType, RelationshipType
from app.services import connector_lifecycle as lifecycle, connector_release_acceptance as service
from app.services import local_release_authority as authority
from app.services.connector_store import PackageStore
from app.services.integration_connections import installed_manifest
from app.services.integration_secrets import AtlasEncryptedSecretProvider
from tests.test_i3_discovery import configured
from tests.test_connector_release_acceptance import public_responses, IDENTITY
from tests.test_connector_qualification import runtime_result

pytestmark = pytest.mark.skipif(os.geteuid() != 0 or not os.getenv("ATLAS_TEST_DATABASE_URL"),
    reason="requires root in disposable container and disposable migrated PostgreSQL")


@pytest.fixture
def db():
    """Committed transactions visible to independent sessions; isolate each test schema."""
    from alembic import command
    from alembic.config import Config
    schema = "local_release_" + secrets.token_hex(8)
    parent = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True)
    with parent.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(parent.url, hide_parameters=True, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with engine.begin() as connection:
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with Session(engine, expire_on_commit=False) as session:
            yield session
    finally:
        engine.dispose()
        with parent.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        parent.dispose()


@pytest.fixture
def unenrolled(db, configured, tmp_path, monkeypatch):
    from atlas_runtime import local_release
    monkeypatch.setenv("ATLAS_BUILD_ID", "a" * 40)
    monkeypatch.setattr(authority, "BINDING", tmp_path / "public/instance.json")
    monkeypatch.setattr(authority, "PRIVATE_KEY", tmp_path / "private/operator.key")
    monkeypatch.setattr(authority, "DEPLOYMENT", tmp_path / "deployment/identity.json")
    monkeypatch.setattr(local_release, "BINDING", authority.BINDING)
    monkeypatch.setattr(local_release, "DEPLOYMENT", authority.DEPLOYMENT)
    store = PackageStore(tmp_path / "acceptance-store")
    monkeypatch.setattr(lifecycle, "package_store", lambda: store)
    for directory in (store.root, authority.BINDING.parent, authority.PRIVATE_KEY.parent, authority.DEPLOYMENT.parent):
        directory.mkdir(mode=0o755, parents=True, exist_ok=True)
    authority.publish(authority.DEPLOYMENT, authority.canonical({"schema": 1, "deployment_id": str(__import__('uuid').uuid4()), "name": "disposable-tests"}))
    report = {"deployment":"disposable-tests", "checked_at":int(time.time()), "checks":{k:True for k in authority.ISOLATION_CHECKS},
              "resources": authority.inspect_resources(db, store.root)}
    return store, report


@pytest.fixture
def staged(db, configured, unenrolled, public_responses):
    store, report = unenrolled
    bound = authority.provision(db, store.root, report)
    stored = asyncio.run(service.stage(db, store.root, IDENTITY))
    row, principal, previous, health = configured
    old = db.get(InstalledConnectorPackage, "i3-fixture")
    old.connector_id = "proxmox"
    row.connector_id = row.plugin_id = "proxmox"
    row.config_json = {"endpoint":"https://example.test", "tls_policy":"verify"}
    AtlasEncryptedSecretProvider(db).replace(row, {"token_id":secrets.token_hex(12), "token_secret":secrets.token_hex(24)})
    choices = []
    for kind, declaration, recommended in service.mappings.declarations(stored.manifest):
        model = AssetType if kind == "asset" else RelationshipType
        if db.scalar(select(model).where(model.key == recommended)) is None:
            db.add(model(key=recommended, name=recommended, active=True, **({} if kind=="asset" else {"directional":True})))
        choices.append({"kind":kind, "source_key":declaration["key"], "target_key":recommended})
    db.flush()
    # The fixture uses the reviewed baseline identity. No runtime health success
    # or source-operation claim is made by these lifecycle tests.
    from app.services.integration_runtime import _approved_baseline
    baseline = _approved_baseline()
    health.update(baseline_version=baseline["baseline_version"], protocol_version=baseline["protocol_version"])
    health["capabilities"].update(dependencies=baseline["dependencies"], collections=baseline["collections"])
    db.commit()
    return store, stored, bound, row, health, choices


def preview(db, staged):
    store, stored, bound, row, health, choices = staged
    with db.begin_nested() as transaction:
        result = service.plan(db, store.root, IDENTITY, health, choices=choices)
        transaction.rollback()
    return result


def runtime(staged, *, failed=False):
    from types import SimpleNamespace
    store, stored, _, _, health, _ = staged
    async def healthy(): return deepcopy(health)
    async def verify(reference):
        if failed: return {"state":"unavailable"}
        return runtime_result(store, stored)
    return SimpleNamespace(health=healthy, verify_connector=verify)


def test_stage_offline_restart_and_explicit_plan_activation_preserve_integrations(db, staged, monkeypatch):
    store, stored, bound, row, health, choices = staged
    before = (row.data_source_id, row.credential_reference)
    assert db.get(InstalledConnectorPackage, "proxmox").version == "1.0.0"
    with pytest.raises(ValueError,match="already_staged"):
        asyncio.run(service.stage(db,store.root,IDENTITY))
    plan = preview(db, staged)
    assert preview(db, staged)["approval"]["plan_digest"] == plan["approval"]["plan_digest"]
    assert row.connector_version == "1.0.0"
    assert not list(db.scalars(select(service.ConnectorMapping).where(service.ConnectorMapping.connector_id=="proxmox")))
    active = asyncio.run(service.activate(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), choices=choices))
    assert active.version == "0.2.2" and row.connector_version == "0.2.2"
    assert (row.data_source_id, row.credential_reference) == before
    def network_forbidden(*args, **kwargs): raise AssertionError("offline path performed network access")
    monkeypatch.setattr(service, "GithubReader", network_forbidden)
    assert PackageStore(store.root).verify_connector(stored.connector_id, stored.version, stored.bundle_digest)["state"] == "verified"
    assert installed_manifest(db, "proxmox")[0].version == "0.2.2"
    assert runtime_result(PackageStore(store.root), stored)["state"] == "verified"
    from app.services import discovery_orchestration as orchestration
    run=asyncio.run(orchestration.create_run(db,row))
    assert run.execution_provenance["connector_digest"]==IDENTITY.sha256
    with pytest.raises(ValueError,match="active_runs"): preview(db,staged)
    service.revoke(store.root, stored.verification["authorization_id"])
    assert (store.root / authority.DIRECTORY / (stored.verification["authorization_id"] + ".json")).exists()
    with pytest.raises(ValueError): installed_manifest(db, "proxmox")
    assert runtime_result(store, stored)["state"] == "unavailable"


@pytest.mark.parametrize("failure", ["missing", "altered", "revoked", "copied", "binding", "forged_method", "writable"])
def test_api_and_runtime_reject_bad_authority(db, staged, failure):
    store, stored, bound, row, health, choices = staged
    path = store.root / authority.DIRECTORY / (stored.verification["authorization_id"] + ".json")
    if failure == "missing": path.unlink()
    elif failure == "revoked": service.revoke(store.root, stored.verification["authorization_id"])
    elif failure == "binding":
        value = json.loads(authority.BINDING.read_bytes()); value["instance_id"] = str(__import__('uuid').uuid4())
        authority.BINDING.chmod(0o644); authority.BINDING.write_bytes(authority.canonical(value)); authority.BINDING.chmod(0o444)
    elif failure == "copied":
        other = store.root.parent / "copied-store"; shutil.copytree(store.root, other)
        store = PackageStore(other)
    elif failure == "forged_method":
        receipt = store._path(stored.connector_id, stored.version, stored.bundle_digest) / "verification.json"
        value=json.loads(receipt.read_bytes()); value["verification"]["method"]="atlas-release-bootstrap"
        receipt.chmod(0o644); receipt.write_bytes(authority.canonical(value)); receipt.chmod(0o444)
    else:
        value=json.loads(path.read_bytes())
        if failure == "altered": value["payload"]["version"]="0.2.3"
        path.chmod(0o644); path.write_bytes(authority.canonical(value))
        if failure != "writable": path.chmod(0o444)
    with pytest.raises(ValueError): store.verify_connector(stored.connector_id, stored.version, stored.bundle_digest)
    assert runtime_result(store, stored)["state"] == "unavailable"


@pytest.mark.parametrize("change", ["integration", "credentials", "runtime", "active", "database", "mapping"])
def test_changed_plan_rejects_approval_and_keeps_previous_active(db, staged, change):
    store, stored, bound, row, health, choices = staged
    plan=preview(db, staged)
    if change=="integration": row.name="Changed dependent"
    elif change=="credentials": AtlasEncryptedSecretProvider(db).replace(row,{"token_id":secrets.token_hex(12),"token_secret":secrets.token_hex(24)})
    elif change=="runtime": health["baseline_digest"]="0"*64
    elif change=="active": db.get(InstalledConnectorPackage,"proxmox").version="1.0.1"
    elif change=="database": db.scalar(select(SystemSetting).where(SystemSetting.key==authority.DATABASE_KEY)).value_={}
    elif change=="mapping": choices[0]["target_key"]="hypervisor_node"
    db.flush()
    expected=db.get(InstalledConnectorPackage,"proxmox").version
    with pytest.raises(ValueError):
        asyncio.run(service.activate(db,store.root,IDENTITY,plan["approval_digest"],runtime(staged),choices=choices))
    assert db.get(InstalledConnectorPackage,"proxmox").version==expected
    assert row.connector_version=="1.0.0"


def test_runtime_verification_failure_preserves_active_mapping_and_credentials(db, staged):
    store, stored, bound, row, health, choices=staged
    plan=preview(db,staged)
    before=(row.data_source_id,row.credential_reference,row.connector_version)
    with pytest.raises(ValueError,match="runtime_verification_failed"):
        asyncio.run(service.activate(db,store.root,IDENTITY,plan["approval_digest"],runtime(staged,failed=True),choices=choices))
    assert (row.data_source_id,row.credential_reference,row.connector_version)==before
    assert db.get(InstalledConnectorPackage,"proxmox").version=="1.0.0"


def test_activation_requires_root_and_exact_approval(db, staged, monkeypatch):
    store, stored, bound, row, health, choices=staged
    with pytest.raises(ValueError,match="explicit_approval"):
        asyncio.run(service.activate(db,store.root,IDENTITY,None,runtime(staged),choices=choices))
    monkeypatch.setattr(authority.os,"geteuid",lambda:10001)
    with pytest.raises(ValueError,match="root_operator"):
        asyncio.run(service.activate(db,store.root,IDENTITY,"0"*64,runtime(staged),choices=choices))


def test_dependency_changed_during_runtime_verification_is_reloaded(db, staged):
    from sqlalchemy import update
    from app.models import Integration
    store, stored, bound, row, health, choices=staged
    plan=preview(db,staged)
    transport=runtime(staged)
    async def verify(reference):
        db.execute(update(Integration).where(Integration.id==row.id).values(name="Concurrent update")
                   .execution_options(synchronize_session=False))
        return runtime_result(store,stored)
    transport.verify_connector=verify
    with pytest.raises(ValueError,match="stale_approval"):
        asyncio.run(service.activate(db,store.root,IDENTITY,plan["approval_digest"],transport,choices=choices))
    assert db.get(InstalledConnectorPackage,"proxmox").version=="1.0.0"


def test_fresh_runtime_offline_execution_admission_and_revocation(db, staged, monkeypatch, tmp_path):
    """Exercise fixed probe admission/materialization; worker output is synthetic.

    No Ansible or source call is made, so this is not operational qualification.
    """
    import uuid
    from atlas_runtime.server import Runtime
    from atlas_runtime import probe, jobs
    store, stored, bound, row, health, choices=staged
    plan=preview(db,staged)
    asyncio.run(service.activate(db,store.root,IDENTITY,plan["approval_digest"],runtime(staged),choices=choices))
    def forbidden(*args,**kwargs): raise AssertionError("offline execution attempted GitHub")
    monkeypatch.setattr(service,"GithubReader",forbidden)
    fresh=Runtime(secrets.token_hex(48),store.root,"development")
    monkeypatch.setattr(fresh,"health",lambda:{"state":"healthy"})
    monkeypatch.setattr(probe,"workspace_root",lambda:tmp_path)
    monkeypatch.setattr(jobs,"stop_process",lambda process:None)
    launches=[]
    class Worker:
        def __init__(self,args,**kwargs):
            assert args[1:3]==["-m","atlas_runtime.probe_worker"]
            self.root=Path(args[-1]); launches.append(args)
            assert (self.root/"project/test_connection.yml").read_bytes()==(
                store._path(stored.connector_id,stored.version,stored.bundle_digest)/"contents/test_connection.yml").read_bytes()
        def communicate(self,data,timeout):
            assert timeout==22 and json.loads(data)["credentials"]
            (self.root/"result.json").write_text(json.dumps({"success":True,"category":"connected","source_version":"9.2.11"}))
    monkeypatch.setattr(probe.subprocess,"Popen",Worker)
    def payload():
        return {"reference":{"connector_id":IDENTITY.connector_id,"version":IDENTITY.version,"digest":IDENTITY.sha256},
                "request_id":str(uuid.uuid4()),"config":row.config_json,
                "local_execution": authority.execution_context(db.get(InstalledConnectorPackage, "proxmox")),
                "credentials":{"token_id":secrets.token_hex(12),"token_secret":secrets.token_hex(24)}}
    try:
        request=payload()
        assert fresh.test_connection(request)["category"]=="connected"
        assert request["credentials"]=={} and len(launches)==1
        service.revoke(store.root,stored.verification["authorization_id"])
        assert fresh.test_connection(payload())["category"]=="package_unavailable"
        assert len(launches)==1 and not list(tmp_path.glob("probe-*"))
    finally:
        fresh.jobs.shutdown()
