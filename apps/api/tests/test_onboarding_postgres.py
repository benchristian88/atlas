"""Exercise scoped APIs and real PostgreSQL transactions on a disposable database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import secrets
from threading import Barrier, Event
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.auth import COOKIE_NAME, create_session_token
from app.database import get_db
from app.main import app
from app.models import (
    AccessAssignment, Asset, AuditEvent, BusinessFunction, Customer, InstallationState,
    Integration, Network, Permission, Role, RolePermission, Service, Site, SiteOnboarding,
    User, Workspace,
)
from app.permissions import CUSTOMER_ADMINISTRATOR, MASTER_ADMINISTRATOR, ROLE_PERMISSION_KEYS, VIEWER
from app.services import onboarding
from app.services.backups import restore_epoch

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")
ENTRY = {"customers.view", "sites.view", "sites.manage"}
CONTEXT = ENTRY | {"customers.manage"}
INVITATION = CONTEXT | {"assets.view", "integrations.view", "networks.view", "services.view", "business_functions.view"}


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_ONBOARDING_PREVIEW", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", secrets.token_hex(48))
    monkeypatch.setenv("ATLAS_STATE_DIR", str(tmp_path / "state"))
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"],
        connect_args={"options": "-c lock_timeout=8000 -c statement_timeout=12000"})
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    slug = uuid4().hex
    user_ids, role_ids, clients = [], [], []

    def database():
        with sessions() as db:
            yield db

    def actor(permissions, scope="global", customer=None, site=None):
        with sessions.begin() as db:
            user = User(email=f"{uuid4().hex}@example.com", display_name="Onboarding tester", password_hash=secrets.token_hex(32))
            role = Role(name=f"Onboarding {uuid4().hex}")
            db.add_all([user, role])
            db.flush()
            user_ids.append(user.id)
            role_ids.append(role.id)
            for key in permissions:
                permission = db.scalar(select(Permission).where(Permission.key == key))
                if permission is None:
                    permission = Permission(name=key, key=key)
                    db.add(permission)
                    db.flush()
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
            grant = AccessAssignment(user_id=user.id, role_id=role.id, scope_type=scope,
                                     customer_id=customer, site_id=site)
            db.add(grant)
            db.flush()
            token = create_session_token(user, restore_epoch=restore_epoch(db))
        client = TestClient(app)
        client.cookies.set(COOKIE_NAME, token)
        clients.append(client)
        return SimpleNamespace(client=client, id=user.id, grant=grant.id)

    app.dependency_overrides[get_db] = database
    with sessions.begin() as db:
        workspace = Workspace(name="Onboarding tests", slug=slug)
        db.add(workspace)
        db.flush()
        marker = db.get(InstallationState, 1)
        original_marker = marker.onboarding_customer_id, marker.onboarding_site_id

    def pair(*, customer=None):
        with sessions.begin() as db:
            if customer is None:
                customer = Customer(workspace_id=workspace.id, name=uuid4().hex)
                db.add(customer)
                db.flush()
            site = Site(customer_id=customer.id, name=uuid4().hex)
            db.add(site)
            db.flush()
        return SimpleNamespace(customer=customer, site=site, path=f"/api/onboarding/{customer.id}/{site.id}")

    try:
        yield SimpleNamespace(actor=actor, pair=pair, sessions=sessions, workspace=workspace)
    finally:
        app.dependency_overrides.pop(get_db, None)
        for client in clients:
            client.close()
        with sessions.begin() as db:
            marker = db.get(InstallationState, 1)
            marker.onboarding_customer_id, marker.onboarding_site_id = original_marker
            db.flush()
            customer_ids = select(Customer.id).where(Customer.workspace_id == workspace.id)
            db.execute(delete(AuditEvent).where(AuditEvent.workspace_id == workspace.id))
            db.execute(delete(SiteOnboarding).where(SiteOnboarding.customer_id.in_(customer_ids)))
            db.execute(delete(AccessAssignment).where(AccessAssignment.user_id.in_(user_ids)))
            db.execute(delete(User).where(User.id.in_(user_ids)))
            db.execute(delete(Role).where(Role.id.in_(role_ids)))
            db.execute(delete(BusinessFunction).where(BusinessFunction.customer_id.in_(customer_ids)))
            db.execute(delete(Network).where(Network.customer_id.in_(customer_ids)))
            db.execute(delete(Site).where(Site.customer_id.in_(customer_ids)))
            db.execute(delete(Customer).where(Customer.workspace_id == workspace.id))
            db.delete(db.get(Workspace, workspace.id))
        engine.dispose()


def confirm(client, path, version=1, profile="homelab"):
    return client.patch(f"{path}/environment", json={"version": version, "environment_profile": profile})


def test_existing_progress_is_shared_versioned_and_resumable_without_domain_writes(env):
    pair = env.pair()
    a, b = env.actor(CONTEXT), env.actor(ENTRY, "customer", pair.customer.id)
    with env.sessions.begin() as db:
        db.add(Network(customer_id=pair.customer.id, site_id=pair.site.id, name="Existing LAN", network_type="lan"))

    def counts():
        with env.sessions() as db:
            return [db.scalar(select(func.count()).select_from(model)) for model in
                    (Customer, Site, Network, Asset, Integration, Service, BusinessFunction)]

    before = counts()
    initial = a.client.get(pair.path).json()
    assert initial["status"] == "not_started"
    assert initial["invitation"]["offered"] is False
    start = a.client.post(f"{pair.path}/start").json()
    assert start["version"] == 1 and start["current_stage"] == "environment"
    assert b.client.post(f"{pair.path}/start").json() == start
    assert b.client.get(pair.path).json()["progress"] == start
    assert confirm(b.client, pair.path, profile="blank").status_code == 200
    assert confirm(a.client, pair.path).status_code == 409
    latest = a.client.get(pair.path).json()["progress"]
    assert latest["environment_profile"] == "blank"
    assert latest["current_stage"] == "capabilities"
    assert latest["stage_decisions"] == {"environment": "completed"}
    assert a.client.patch(f"{pair.path}/environment", json={
        "version": 2, "environment_profile": "homelab", "stage_decisions": {"showcase": "completed"},
    }).status_code == 422
    assert a.client.post(f"{pair.path}/save", json={"version": 1}).status_code == 409
    saved = a.client.post(f"{pair.path}/save", json={"version": 2}).json()
    assert saved["status"] == "saved" and saved["version"] == 3
    assert b.client.post(f"{pair.path}/start").json() == saved
    assert b.client.get(pair.path).json()["progress"] == saved
    assert b.client.post(f"{pair.path}/resume", json={"version": 2}).status_code == 409
    resumed = b.client.post(f"{pair.path}/resume", json={"version": 3}).json()
    assert resumed["current_stage"] == "capabilities"
    assert resumed["status"] == "in_progress" and resumed["version"] == 4
    assert b.client.post(f"{pair.path}/resume", json={"version": 3}).json() == resumed
    assert resumed["completed_at"] is None
    assert counts() == before

    with env.sessions() as db:
        state = onboarding.progress(db, pair.site)
        assert state.last_actor_id == b.id
        audits = db.execute(select(AuditEvent.event_type, AuditEvent.user_id).where(
            AuditEvent.target_id == pair.site.id, AuditEvent.event_type.like("onboarding.%"),
        )).all()
        assert set(audits) == {
            ("onboarding.started", a.id), ("onboarding.environment_confirmed", b.id),
            ("onboarding.saved", a.id), ("onboarding.resumed", b.id),
        }


def test_site_scope_header_forgery_and_revocation(env):
    pair = env.pair()
    sibling = env.pair(customer=pair.customer)
    other = env.pair()
    a = env.actor(CONTEXT, "site", pair.customer.id, pair.site.id)
    headers = {"X-Atlas-Customer-ID": str(other.customer.id), "X-Atlas-Site-ID": str(other.site.id)}
    assert a.client.get(pair.path, headers=headers).status_code == 200
    mismatched = f"/api/onboarding/{pair.customer.id}/{other.site.id}"
    for path in (sibling.path, other.path, mismatched):
        assert a.client.get(path, headers=headers).json() == {"detail": "Record not found"}
        assert a.client.post(f"{path}/start", headers=headers).status_code == 404
    options = a.client.get("/api/onboarding/contexts").json()
    assert options["sites"] == [{"id": str(pair.site.id), "name": pair.site.name, "customer_id": str(pair.customer.id), "status": "not_started"}]
    assert options["customers"][0]["can_add_site"] is False
    assert options["can_add_customer"] is False
    assert a.client.patch(f"/api/customers/{pair.customer.id}", json={"name": "No"}).status_code == 404
    assert a.client.post("/api/sites", json={"name": "No", "customer_id": str(pair.customer.id)}).status_code == 404
    assert a.client.patch(f"/api/sites/{pair.site.id}", json={"name": "Allowed"}).status_code == 200
    assert a.client.post(f"{pair.path}/start").status_code == 200
    with env.sessions.begin() as db:
        db.execute(delete(AccessAssignment).where(AccessAssignment.id == a.grant))
    assert a.client.get(pair.path).status_code == 403
    assert confirm(a.client, pair.path).status_code == 403
    assert a.client.post(f"{pair.path}/resume", json={"version": 1}).status_code == 403


def test_context_creation_can_resume_after_independent_site_failure(env):
    a = env.actor(CONTEXT).client
    customer = a.post("/api/customers", json={"name": "Customer without a Site", "workspace_id": str(env.workspace.id)}).json()
    assert a.post("/api/sites", json={"name": "", "customer_id": customer["id"]}).status_code == 422
    scoped = env.actor(CONTEXT, "customer", customer["id"]).client
    directory = scoped.get("/api/onboarding/contexts").json()
    assert directory["customers"] == [{"id": customer["id"], "name": customer["name"], "can_add_site": True}]
    assert directory["sites"] == [] and not directory["can_add_customer"]
    site_payload = {"name": "Explicit Site", "customer_id": customer["id"]}
    site = scoped.post("/api/sites", json=site_payload)
    assert site.status_code == 201
    assert scoped.post("/api/sites", json=site_payload).status_code == 409
    available = scoped.get("/api/onboarding/contexts").json()["sites"]
    assert [row["id"] for row in available] == [site.json()["id"]]


def test_viewer_reads_and_dismisses_without_shared_write_access(env):
    pair = env.pair()
    sibling = env.pair(customer=pair.customer)
    outside = env.pair()
    with env.sessions.begin() as db:
        marker = db.get(InstallationState, 1)
        marker.onboarding_customer_id, marker.onboarding_site_id = pair.customer.id, pair.site.id
    viewer = env.actor(ROLE_PERMISSION_KEYS[VIEWER], "customer", pair.customer.id).client
    manager = env.actor(ENTRY, "site", pair.customer.id, pair.site.id).client
    customer_admin = env.actor(ROLE_PERMISSION_KEYS[CUSTOMER_ADMINISTRATOR], "customer", pair.customer.id).client
    global_admin = env.actor(ROLE_PERMISSION_KEYS[MASTER_ADMINISTRATOR]).client
    assert viewer.get(pair.path).json()["can_manage"] is False
    assert viewer.get(pair.path).json()["invitation"]["offered"] is True
    assert viewer.get("/api/onboarding/contexts").json()["sites"] == []
    assert viewer.post(f"{pair.path}/invitation/dismiss").status_code == 204
    assert viewer.get(pair.path).json()["invitation"]["dismissed"] is True
    assert viewer.get(outside.path).json() == {"detail": "Record not found"}
    assert viewer.post(f"{outside.path}/invitation/dismiss").status_code == 404
    assert manager.get(pair.path).json()["can_manage"] is True
    assert manager.get(sibling.path).status_code == 404
    assert customer_admin.get(sibling.path).json()["can_manage"] is True
    assert customer_admin.get(outside.path).status_code == 404
    assert global_admin.get(outside.path).json()["can_manage"] is True
    assert global_admin.get(f"/api/onboarding/{outside.customer.id}/{pair.site.id}").status_code == 404
    assert viewer.post(f"{pair.path}/start").status_code == 404
    assert viewer.post(f"{pair.path}/save", json={"version": 0, "draft_profile": "blank"}).status_code == 404
    assert manager.post(f"{pair.path}/start").status_code == 200
    assert customer_admin.post(f"{pair.path}/save", json={"version": 1, "draft_profile": "blank"}).status_code == 200
    assert viewer.get(pair.path).json()["progress"]["draft_profile"] == "blank"
    assert confirm(viewer, pair.path, version=2).status_code == 404
    for action in ("save", "resume"):
        assert viewer.post(f"{pair.path}/{action}", json={"version": 2}).status_code == 404
    assert global_admin.post(f"{pair.path}/resume", json={"version": 2}).status_code == 200


def test_draft_save_is_versioned_attributed_and_requires_confirmation(env):
    pair = env.pair()
    a, b = env.actor(ENTRY), env.actor(ENTRY, "customer", pair.customer.id)

    def counts():
        models = (Customer, Site, Asset, Integration, Network, Service, BusinessFunction)
        with env.sessions() as db:
            return [db.scalar(select(func.count()).select_from(model)) for model in models]

    before = counts()
    payload = {"version": 0, "draft_profile": "blank"}
    response = a.client.post(f"{pair.path}/save", json=payload)
    assert response.status_code == 200
    draft = response.json()
    assert (draft["draft_profile"], draft["environment_profile"], draft["current_stage"]) == ("blank", None, "environment")
    assert (draft["status"], draft["version"], draft["stage_decisions"]) == ("saved", 1, {})
    assert b.client.post(f"{pair.path}/save", json={**payload, "draft_profile": "homelab"}).status_code == 409
    assert b.client.get(pair.path).json()["progress"] == draft
    with env.sessions() as db:
        state = onboarding.progress(db, pair.site)
        assert state.draft_only and state.last_actor_id == a.id
        event = db.scalar(select(AuditEvent).where(
            AuditEvent.site_id == pair.site.id, AuditEvent.event_type == "onboarding.saved",
        ))
        assert event.user_id == a.id
    assert confirm(a.client, pair.path, profile="blank").status_code == 409
    resumed = b.client.post(f"{pair.path}/resume", json={"version": 1}).json()
    assert (resumed["draft_profile"], resumed["environment_profile"], resumed["current_stage"]) == ("blank", None, "environment")
    assert a.client.post(f"{pair.path}/save", json={"version": 1, "draft_profile": "homelab"}).status_code == 409
    confirmed = confirm(b.client, pair.path, version=resumed["version"], profile="blank").json()
    assert (confirmed["draft_profile"], confirmed["environment_profile"], confirmed["current_stage"]) == (None, "blank", "capabilities")
    assert counts() == before


def test_draft_only_does_not_block_site_transfer_or_deletion(env):
    original, target, unused = env.pair(), env.pair(), env.pair()
    admin = env.actor(CONTEXT).client
    draft_ids = []
    for pair in (original, unused):
        saved = admin.post(f"{pair.path}/save", json={"version": 0, "draft_profile": "blank"})
        assert saved.status_code == 200
        with env.sessions() as db:
            draft_ids.append(onboarding.progress(db, pair.site).id)
    try:
        response = admin.patch(f"/api/sites/{original.site.id}", json={"customer_id": str(target.customer.id)})
        assert response.status_code == 200, response.text
        assert admin.get(original.path).status_code == 404
        assert admin.get(f"/api/onboarding/{target.customer.id}/{original.site.id}").json()["progress"] is None
        assert admin.delete(f"/api/sites/{unused.site.id}").status_code == 204
        with env.sessions() as db:
            for draft_id in draft_ids:
                state = db.get(SiteOnboarding, draft_id)
                assert (state.customer_id, state.site_id) == (None, None)
    finally:
        with env.sessions.begin() as db:
            db.execute(delete(SiteOnboarding).where(SiteOnboarding.id.in_(draft_ids)))


def test_invitation_ignores_tombstones_but_detects_visible_records(env):
    pair = env.pair()
    with env.sessions.begin() as db:
        marker = db.get(InstallationState, 1)
        marker.onboarding_customer_id, marker.onboarding_site_id = pair.customer.id, pair.site.id
        db.add(BusinessFunction(
            customer_id=pair.customer.id, site_id=pair.site.id, name="Retained function",
            active=False, deleted_at=datetime.now(timezone.utc),
        ))
    actor = env.actor(INVITATION, "customer", pair.customer.id).client
    assert actor.get(pair.path).json()["invitation"]["offered"] is True
    with env.sessions.begin() as db:
        db.add(BusinessFunction(customer_id=pair.customer.id, name="Live customer-wide function"))
    assert actor.get(pair.path).json()["invitation"] == {"offered": False, "dismissed": False}
    assert actor.get("/api/onboarding/contexts").json()["sites"][0]["status"] == "not_started"
    assert actor.post(f"{pair.path}/start").status_code == 200


def test_dismissal_is_personal_and_does_not_start_the_site(env):
    pair = env.pair()
    with env.sessions.begin() as db:
        marker = db.get(InstallationState, 1)
        marker.onboarding_customer_id = pair.customer.id
        marker.onboarding_site_id = pair.site.id
    a, b = (env.actor(INVITATION, "customer", pair.customer.id) for _ in range(2))
    scoped = env.actor(INVITATION, "site", pair.customer.id, pair.site.id)
    assert scoped.client.get(pair.path).json()["invitation"]["offered"] is False
    assert a.client.get(pair.path).json()["invitation"]["offered"] is True
    for _ in range(2):
        assert a.client.post(f"{pair.path}/invitation/dismiss").status_code == 204
    assert a.client.get(pair.path).json()["invitation"] == {"offered": False, "dismissed": True}
    assert b.client.get(pair.path).json()["invitation"] == {"offered": True, "dismissed": False}
    assert b.client.get(pair.path).json()["status"] == "not_started"
    assert a.client.post(f"{pair.path}/start").status_code == 200
    assert b.client.get(pair.path).json()["status"] == "in_progress"
    with env.sessions() as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.site_id == pair.site.id, AuditEvent.event_type == "onboarding.invitation_dismissed",
        )) == 1


def test_competing_starts_and_progress_use_independent_transactions(env, monkeypatch):
    pair = env.pair()
    a, b = env.actor(ENTRY), env.actor(ENTRY)
    barrier = Barrier(2, timeout=8)
    original_start = onboarding.start

    def simultaneous_start(*args):
        barrier.wait()
        return original_start(*args)

    monkeypatch.setattr(onboarding, "start", simultaneous_start)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda actor: actor.client.post(f"{pair.path}/start"), (a, b)))
    assert [result.status_code for result in results] == [200, 200]
    assert results[0].json() == results[1].json()
    with env.sessions() as db:
        assert db.scalar(select(func.count()).select_from(SiteOnboarding).where(SiteOnboarding.site_id == pair.site.id)) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.site_id == pair.site.id, AuditEvent.event_type == "onboarding.started",
        )) == 1

    original_update = onboarding.update

    def simultaneous_update(*args, **kwargs):
        barrier.wait()
        return original_update(*args, **kwargs)

    monkeypatch.setattr(onboarding, "update", simultaneous_update)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda actor: confirm(actor.client, pair.path), (a, b)))
    assert sorted(result.status_code for result in results) == [200, 409]
    assert b.client.get(pair.path).json()["progress"]["version"] == 2


def test_used_context_cannot_be_deleted_or_transferred(env):
    pair = env.pair()
    target = env.pair()
    actor = env.actor(CONTEXT).client
    assert actor.post(f"{pair.path}/start").status_code == 200
    assert actor.delete(f"/api/sites/{pair.site.id}").status_code == 409
    assert actor.patch(f"/api/sites/{pair.site.id}", json={"customer_id": str(target.customer.id)}).status_code == 409
    with pytest.raises(IntegrityError), env.sessions.begin() as db:
        db.execute(update(Site).where(Site.id == pair.site.id).values(customer_id=target.customer.id))
    with pytest.raises(IntegrityError), env.sessions.begin() as db:
        db.add(SiteOnboarding(customer_id=pair.customer.id, site_id=target.site.id))
        db.flush()


@pytest.mark.parametrize("action", ["environment", "resume"])
def test_permission_revoked_while_progress_write_waits_for_lock(env, monkeypatch, action):
    pair = env.pair()
    actor = env.actor(ENTRY, "site", pair.customer.id, pair.site.id)
    assert actor.client.post(f"{pair.path}/start").status_code == 200
    version = 1
    if action == "resume":
        assert actor.client.post(f"{pair.path}/save", json={"version": version}).status_code == 200
        version += 1
    attempting_lock = Event()
    original_progress = onboarding.progress

    def notify_progress(db, site, *, lock=False):
        if lock:
            attempting_lock.set()
        return original_progress(db, site, lock=lock)

    monkeypatch.setattr(onboarding, "progress", notify_progress)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with env.sessions.begin() as db:
            original_progress(db, pair.site, lock=True)
            if action == "environment":
                pending = pool.submit(confirm, actor.client, pair.path, version=version)
            else:
                pending = pool.submit(actor.client.post, f"{pair.path}/resume", json={"version": version})
            assert attempting_lock.wait(timeout=5)
            db.execute(delete(AccessAssignment).where(AccessAssignment.id == actor.grant))
        assert pending.result(timeout=5).status_code == 404
    with env.sessions() as db:
        assert onboarding.progress(db, pair.site).version == version


def test_bootstrap_marker_alone_clears_on_unused_site_transfer(env):
    original = env.pair()
    destination = env.pair()
    with env.sessions.begin() as db:
        marker = db.get(InstallationState, 1)
        marker.onboarding_customer_id = original.customer.id
        marker.onboarding_site_id = original.site.id
    actor = env.actor(CONTEXT).client
    moved = actor.patch(f"/api/sites/{original.site.id}", json={"customer_id": str(destination.customer.id)})
    assert moved.status_code == 200 and moved.json()["id"] == str(original.site.id)
    with env.sessions() as db:
        marker = db.get(InstallationState, 1)
        assert (marker.onboarding_customer_id, marker.onboarding_site_id) == (None, None)
