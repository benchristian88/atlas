import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.authorization import ActiveContext, Principal, ScopeGrant, get_principal, scope_condition
from app.database import get_db
from app.main import app
from app.models import Asset, Customer, User
from app.routes.asset_relationships import create_asset_relationship
from app.routes.assets import create_asset, get_asset, list_assets
from app.routes.context import dashboard_summary
from app.routes.manual_assets import list_manual_assets
from app.routes.networks import list_networks
from app.routes.topology import get_topology
from app.schemas import AssetRelationshipCreate, ManualAssetCreate


def user(email="user@example.com") -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email=email,
        display_name="Test User",
        password_hash="unused",
        is_active=True,
        force_password_change=False,
        failed_login_count=0,
        session_version=1,
        auth_provider="local",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
    )


def principal(
    permissions: set[str],
    *,
    scope_type="global",
    customer_id=None,
    site_id=None,
) -> Principal:
    return Principal(
        user=user(),
        grants=(
            ScopeGrant(
                assignment_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                role_name="Test Role",
                scope_type=scope_type,
                customer_id=customer_id,
                site_id=site_id,
                permissions=frozenset(permissions),
            ),
        ),
    )


def request(method="POST") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/test",
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
        }
    )


class EmptyDatabase:
    def __init__(self, records=()):
        self.records = {(type(item), item.id): item for item in records}
        self.statements = []

    def get(self, model, record_id):
        return self.records.get((model, record_id))

    def scalar(self, statement):
        self.statements.append(str(statement))
        return 0

    def scalars(self, statement):
        self.statements.append(str(statement))
        return []

    def execute(self, statement):
        self.statements.append(str(statement))
        return []

    def add(self, record):
        return None

    def flush(self):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None

    def refresh(self, record):
        return None


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_master_administrator_has_global_access() -> None:
    master = principal({"assets.view", "assets.edit", "audit.view"})
    assert master.can("assets.view", uuid.uuid4(), uuid.uuid4())
    assert master.can("audit.view", None, None)


def test_global_reference_permission_does_not_unlock_customer_context() -> None:
    reference_editor = principal({"asset_types.view"})
    assert reference_editor.has_global_access
    assert not reference_editor.has_global_context_access
    assert not reference_editor.can_access_context(uuid.uuid4(), uuid.uuid4())


def test_customer_administrator_is_limited_to_assigned_customer() -> None:
    customer_a = uuid.uuid4()
    customer_b = uuid.uuid4()
    admin = principal(
        {"assets.view", "assets.edit"},
        scope_type="customer",
        customer_id=customer_a,
    )
    assert admin.can("assets.edit", customer_a, uuid.uuid4())
    assert not admin.can("assets.view", customer_b, uuid.uuid4())


def test_site_viewer_is_read_only_and_site_limited() -> None:
    customer_id = uuid.uuid4()
    site_id = uuid.uuid4()
    viewer = principal(
        {"assets.view"},
        scope_type="site",
        customer_id=customer_id,
        site_id=site_id,
    )
    assert viewer.can("assets.view", customer_id, site_id)
    assert not viewer.can("assets.view", customer_id, uuid.uuid4())
    assert not viewer.can_anywhere("assets.edit")


def test_viewer_mutation_is_blocked_by_backend() -> None:
    viewer = principal({"assets.view"})
    db = EmptyDatabase()
    app.dependency_overrides[get_principal] = lambda: viewer
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        response = client.post(
            "/api/assets",
            json={
                "customer_id": str(uuid.uuid4()),
                "site_id": str(uuid.uuid4()),
                "name": "forbidden",
                "asset_type": "server",
            },
        )
    assert response.status_code == 403


def test_manual_object_id_substitution_is_hidden() -> None:
    customer_a, customer_b, site_b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    scoped_user = principal(
        {"assets.view"}, scope_type="customer", customer_id=customer_a
    )
    asset = Asset(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        customer_id=customer_b,
        site_id=site_b,
        name="customer-b-secret",
        asset_type="server",
        source="manual",
        metadata_={},
    )
    with pytest.raises(HTTPException) as exc_info:
        get_asset(asset.id, scoped_user, EmptyDatabase([asset]))
    assert exc_info.value.status_code == 404


def test_scope_predicate_contains_customer_boundary() -> None:
    customer_id = uuid.uuid4()
    scoped_user = principal(
        {"assets.view"}, scope_type="customer", customer_id=customer_id
    )
    compiled = str(scope_condition(scoped_user, "assets.view", Asset.customer_id, Asset.site_id))
    assert "assets.customer_id IN" in compiled


def test_topology_builds_backend_scope_predicates() -> None:
    customer_id = uuid.uuid4()
    scoped_user = principal(
        {
            "customers.view",
            "sites.view",
            "assets.view",
            "relationships.view",
            "networks.view",
        },
        scope_type="customer",
        customer_id=customer_id,
    )
    db = EmptyDatabase()
    response = get_topology(ActiveContext(customer_id, None), scoped_user, db)
    assert response["assets"] == []
    sql = "\n".join(db.statements)
    assert "assets.customer_id IN" in sql
    assert "asset_relationships" in sql
    assert "JOIN assets AS" in sql


def test_dashboard_counts_are_computed_with_scope_filters() -> None:
    customer_id = uuid.uuid4()
    scoped_user = principal(
        {
            "customers.view",
            "sites.view",
            "assets.view",
            "relationships.view",
            "networks.view",
        },
        scope_type="customer",
        customer_id=customer_id,
    )
    db = EmptyDatabase()
    summary = dashboard_summary(ActiveContext(customer_id, None), scoped_user, db)
    assert summary == {
        "customers": 0,
        "sites": 0,
        "assets": 0,
        "networks": 0,
        "relationships": 0,
        "reconciliation": 0,
    }
    assert all("WHERE" in statement for statement in db.statements)


def test_asset_creation_must_match_active_context() -> None:
    expected_customer, expected_site = uuid.uuid4(), uuid.uuid4()
    master = principal({"assets.create"})
    payload = ManualAssetCreate(
        customer_id=uuid.uuid4(),
        site_id=expected_site,
        name="wrong-customer",
        asset_type="server",
    )
    with pytest.raises(HTTPException) as exc_info:
        create_asset(
            payload,
            request(),
            ActiveContext(expected_customer, expected_site),
            master,
            EmptyDatabase(),
        )
    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    "list_route",
    [list_assets, list_manual_assets, list_networks],
)
def test_list_query_cannot_override_active_customer_context(list_route) -> None:
    active_customer = uuid.uuid4()
    with pytest.raises(HTTPException) as exc_info:
        list_route(
            ActiveContext(active_customer, None),
            principal({"assets.view", "networks.view"}),
            customer_id=uuid.uuid4(),
            site_id=None,
            limit=100,
            offset=0,
            db=EmptyDatabase(),
        )
    assert exc_info.value.status_code == 403


def test_cross_site_and_cross_customer_relationships_are_rejected() -> None:
    customer_id = uuid.uuid4()
    source = Asset(
        id=uuid.uuid4(), workspace_id=uuid.uuid4(), customer_id=customer_id,
        site_id=uuid.uuid4(), name="source", asset_type="server", source="manual", metadata_={},
    )
    target = Asset(
        id=uuid.uuid4(), workspace_id=source.workspace_id, customer_id=customer_id,
        site_id=uuid.uuid4(), name="target", asset_type="server", source="manual", metadata_={},
    )
    master = principal({"relationships.create"})
    with pytest.raises(HTTPException) as exc_info:
        create_asset_relationship(
            AssetRelationshipCreate(
                source_asset_id=source.id,
                target_asset_id=target.id,
                relationship_type="depends_on",
            ),
            request(),
            ActiveContext(None, None),
            master,
            EmptyDatabase([source, target]),
        )
    assert exc_info.value.status_code == 422


def test_openapi_exposes_administration_and_reference_endpoints() -> None:
    paths = app.openapi()["paths"]
    for path in (
        "/api/users",
        "/api/roles",
        "/api/permissions",
        "/api/asset-types",
        "/api/relationship-types",
        "/api/custom-fields",
        "/api/audit-events",
        "/api/context",
        "/api/dashboard/summary",
        "/api/customers",
        "/api/sites",
        "/api/assets",
        "/api/asset-relationships",
        "/api/networks",
        "/api/asset-interfaces",
        "/api/manual-assets",
        "/api/topology",
    ):
        assert path in paths
    assert all(path.startswith("/api/") for path in paths)
    for old_path in ("/customers", "/sites", "/assets", "/topology"):
        assert old_path not in paths
