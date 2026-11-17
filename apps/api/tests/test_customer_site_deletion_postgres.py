"""AT-B03: real migrated PostgreSQL, API workflows and database-loaded grants.

Only get_db is overridden to select the disposable database. Authentication uses
signed test sessions; permissions and scope load from actual persisted grants.
The late-insertion test commits a second real API transaction after guard reads.
"""
import hashlib
import os
import secrets
from types import SimpleNamespace
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.auth import COOKIE_NAME, create_session_token
from app.database import get_db
from app.models import AccessAssignment, AuditEvent, CriticalityLevel, Customer, Permission, Role, RolePermission, ServiceType, Site, User, Workspace
from app.routes import business_functions, customers, networks, services, sites
from app.services.backups import restore_epoch

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET_KEY", secrets.token_hex(32))
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True,
        connect_args={"options": "-c lock_timeout=5000 -c statement_timeout=10000"})
    # Dedicated class keeps flush hooks local to this test's request sessions.
    request_session = type("ParentDeletionSession", (Session,), {})
    sessions = sessionmaker(bind=engine, class_=request_session, autoflush=False, expire_on_commit=False)
    app = FastAPI()
    for router in (customers.router, sites.router, networks.router, business_functions.router, services.router):
        app.include_router(router, prefix="/api")
    def get_test_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = get_test_db
    clients = []

    def client(permissions, scope="global", customer_id=None, site_id=None):
        with sessions.begin() as db:
            actor = User(email=f"{uuid.uuid4().hex}@example.com", display_name="AT-B03 operator",
                password_hash=secrets.token_hex(32), is_active=True, force_password_change=False)
            role = Role(name=f"AT-B03 {uuid.uuid4().hex}", active=True)
            db.add_all([actor, role]); db.flush()
            for key in permissions:
                permission = db.scalar(select(Permission).where(Permission.key == key))
                if permission is None:
                    permission = Permission(key=key, name=key)
                    db.add(permission); db.flush()
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
            db.add(AccessAssignment(user_id=actor.id, role_id=role.id, scope_type=scope,
                customer_id=customer_id, site_id=site_id))
            db.flush()
            token = create_session_token(actor, restore_epoch=restore_epoch(db))
        result = TestClient(app)
        result.cookies.set(COOKIE_NAME, token)
        clients.append(result)
        return result

    manager_permissions = {"customers.view", "customers.manage", "sites.view", "sites.manage"}
    operator = client(manager_permissions | {"networks.create", "networks.view", "business_functions.manage", "business_functions.view",
        "services.create", "services.view", "services.archive"})
    with sessions.begin() as db:
        workspace = Workspace(name="AT-B03", slug=uuid.uuid4().hex)
        db.add(workspace); db.flush()
    def create_customer():
        response = operator.post("/api/customers", json={"workspace_id": str(workspace.id), "name": f"Customer {uuid.uuid4().hex}"})
        assert response.status_code == 201, response.text
        return response.json()
    def create_site(customer):
        response = operator.post("/api/sites", json={"customer_id": customer["id"], "name": f"Site {uuid.uuid4().hex}"})
        assert response.status_code == 201, response.text
        return response.json()
    def target(kind):
        customer = create_customer()
        obj = customer if kind == "customer" else create_site(customer)
        return SimpleNamespace(kind=kind, obj=obj, customer=customer, model=Customer if kind == "customer" else Site,
            path=f"/api/{kind}s/{obj['id']}", customer_id=customer["id"], site_id=None if kind == "customer" else obj["id"])
    def add_network(target, api=operator):
        response = api.post("/api/networks", json={"customer_id": target.customer_id, "site_id": target.site_id,
            "name": f"Network {uuid.uuid4().hex}", "network_type": "vlan"})
        assert response.status_code == 201, response.text
        return response.json()
    yield SimpleNamespace(engine=engine, sessions=sessions, session_class=request_session, client=operator,
        client_for=client, manager_permissions=manager_permissions, target=target, add_network=add_network)
    for api in clients: api.close()
    app.dependency_overrides.clear()
    engine.dispose()


def dependency_body(kind):
    return {"detail": f"This {kind.title()} can't be deleted because other records or retained history depend on it. To stop using it, set its status to Inactive."}


def snapshot(engine):
    """Compare all public rows without exposing credentials or full row values."""
    with engine.connect() as db:
        tables = db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).scalars().all()
        result = {}
        for table in tables:
            rows = sorted(db.execute(text(f'SELECT row_to_json(t)::text FROM "{table}" t')).scalars())
            result[table] = (len(rows), hashlib.sha256("\n".join(rows).encode()).hexdigest())
        return result


@pytest.mark.parametrize("kind", ["customer", "site"])
def test_api_created_unused_parent_deletes_and_retains_audit(env, kind):
    target = env.target(kind)
    before = snapshot(env.engine)
    response = env.client.delete(target.path)
    assert response.status_code == 204 and response.content == b""
    after = snapshot(env.engine)
    assert {table: after[table][0] - before[table][0] for table in before if after[table][0] != before[table][0]} == {f"{kind}s": -1, "audit_events": 1}
    with env.sessions() as db:
        assert db.get(target.model, uuid.UUID(target.obj["id"])) is None
        audits = list(db.scalars(select(AuditEvent).where(AuditEvent.target_id == uuid.UUID(target.obj["id"])).order_by(AuditEvent.created_at)))
        assert [a.event_type for a in audits] == [f"{kind}.created", f"{kind}.deleted"]
        assert all(a.metadata_["name"] == target.obj["name"] and a.actor_display_name == "AT-B03 operator" for a in audits)
        assert all(a.site_id is None for a in audits)
        if kind == "customer": assert all(a.customer_id is None for a in audits)
        else: assert all(str(a.customer_id) == target.customer_id for a in audits)


@pytest.mark.parametrize("kind", ["customer", "site"])
@pytest.mark.parametrize("in_use", [False, True])
def test_inactive_status_preserves_existing_deletion_rules(env, kind, in_use):
    target = env.target(kind)
    if in_use: env.add_network(target)
    updated = env.client.patch(target.path, json={"status": "inactive", "name": target.obj["name"] + " edited"})
    assert updated.status_code == 200
    before = snapshot(env.engine)
    response = env.client.delete(target.path)
    if in_use:
        assert response.status_code == 409 and response.json() == dependency_body(kind)
        assert snapshot(env.engine) == before
    else:
        assert response.status_code == 204
        with env.sessions() as db:
            audits = list(db.scalars(select(AuditEvent).where(AuditEvent.target_id == uuid.UUID(target.obj["id"])).order_by(AuditEvent.created_at)))
            assert [a.event_type for a in audits] == [f"{kind}.created", f"{kind}.updated", f"{kind}.deleted"]
            assert audits[0].metadata_["name"] == target.obj["name"]
            assert audits[-1].metadata_["name"] == updated.json()["name"]


@pytest.mark.parametrize("kind", ["customer", "site"])
@pytest.mark.parametrize("blocker", ["network", "business_function", "retained_business_function", "service", "retained_service", "access_assignment"])
def test_guard_and_database_refusals_are_identical_and_atomic(env, kind, blocker):
    target = env.target(kind)
    if blocker == "network":
        env.add_network(target)
    elif blocker == "access_assignment":
        env.client_for({"customers.view"}, scope=kind, customer_id=uuid.UUID(target.customer_id),
            site_id=uuid.UUID(target.site_id) if target.site_id else None)
    else:
        collection = "services" if blocker in {"service", "retained_service"} else "business-functions"
        payload = {"customer_id": target.customer_id, "site_id": target.site_id, "name": f"Capability {uuid.uuid4().hex}"}
        if collection == "services":
            with env.sessions() as db:
                payload.update(service_type_id=str(db.scalar(select(ServiceType.id).where(ServiceType.active.is_(True)).order_by(ServiceType.id))),
                    criticality_level_id=str(db.scalar(select(CriticalityLevel.id).where(CriticalityLevel.active.is_(True)).order_by(CriticalityLevel.id))))
        created = env.client.post(f"/api/{collection}", json=payload)
        assert created.status_code == 201, created.text
        if blocker.startswith("retained_"):
            assert env.client.delete(f"/api/{collection}/{created.json()['id']}").status_code == 204
            assert env.client.get(f"/api/{collection}/{created.json()['id']}").status_code == 404
    # Parent manager cannot read either dependency, but must get the same safe error.
    manager = env.client_for(env.manager_permissions)
    assert manager.get("/api/networks").status_code == 403
    assert manager.get("/api/business-functions").status_code == 403
    assert manager.get("/api/services").status_code == 403
    before = snapshot(env.engine)
    response = manager.delete(target.path)
    assert response.status_code == 409
    assert response.json() == dependency_body(kind)
    assert snapshot(env.engine) == before
    with env.sessions() as db:
        assert not db.scalar(select(AuditEvent.id).where(AuditEvent.target_id == uuid.UUID(target.obj["id"]), AuditEvent.event_type == f"{kind}.deleted"))


@pytest.mark.parametrize("kind", ["customer", "site"])
def test_missing_scope_and_permission_responses(env, kind):
    target = env.target(kind)
    other = env.target(kind)
    scoped = env.client_for(env.manager_permissions, scope=kind, customer_id=uuid.UUID(other.customer_id),
        site_id=uuid.UUID(other.site_id) if other.site_id else None)
    reader = env.client_for({"customers.view", "sites.view"})
    missing = f"/api/{kind}s/{uuid.uuid4()}"
    before = snapshot(env.engine)
    hidden = scoped.delete(target.path)
    absent = scoped.delete(missing)
    assert hidden.status_code == absent.status_code == 404
    assert hidden.json() == absent.json() == {"detail": "Record not found"}
    for path in (target.path, missing):
        refused = reader.delete(path)
        assert refused.status_code == 403
        assert refused.json() == {"detail": "You do not have permission to perform this action"}
    assert snapshot(env.engine) == before


def test_site_assignment_cannot_delete_a_sibling_in_the_same_customer(env):
    target = env.target("site")
    sibling = env.client.post("/api/sites", json={"customer_id": target.customer_id, "name": "Other site"})
    assert sibling.status_code == 201
    scoped = env.client_for(env.manager_permissions, scope="site", customer_id=uuid.UUID(target.customer_id),
        site_id=uuid.UUID(sibling.json()["id"]))
    before = snapshot(env.engine)
    response = scoped.delete(target.path)
    assert response.status_code == 404 and response.json() == {"detail": "Record not found"}
    assert snapshot(env.engine) == before


@pytest.mark.parametrize("kind", ["customer", "site"])
def test_real_api_dependency_commit_after_guard_reaches_safe_fk_fallback(env, kind):
    target = env.target(kind)
    guard_reads, inserted, committed_state = [], [], []
    writer = env.client_for(env.manager_permissions | {"networks.create", "networks.view"})
    def observe_guard(conn, cursor, statement, parameters, context, many):
        if statement.startswith("SELECT count(") and "FROM networks" in statement:
            guard_reads.append(statement)
    def insert_after_guard(db, flush_context, instances):
        if inserted or not any(isinstance(row, target.model) and str(row.id) == target.obj["id"] for row in db.deleted):
            return
        assert guard_reads, "Network guard must run before the independent insert"
        inserted.append(env.add_network(target, writer))
        committed_state.append(snapshot(env.engine))
    event.listen(env.engine, "before_cursor_execute", observe_guard)
    event.listen(env.session_class, "before_flush", insert_after_guard)
    try:
        response = env.client.delete(target.path)
    finally:
        event.remove(env.session_class, "before_flush", insert_after_guard)
        event.remove(env.engine, "before_cursor_execute", observe_guard)
    assert len(inserted) == 1
    assert response.status_code == 409 and response.json() == dependency_body(kind)
    # Includes the independently committed Network, but no partial deletion/audit.
    assert snapshot(env.engine) == committed_state[0]
    assert env.client.get(target.path).status_code == 200
    assert env.client.get(f"/api/networks/{inserted[0]['id']}").status_code == 200
