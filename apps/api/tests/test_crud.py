import uuid
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException

from app.main import app
from app.models import Asset, Customer, Site, User, Workspace
from app.routes.customers import create_customer, delete_customer, update_customer
from app.routes.manual_assets import (
    create_manual_asset,
    delete_manual_asset,
    get_manual_asset,
    update_manual_asset,
)
from app.routes.sites import create_site, delete_site, update_site
from app.schemas import (
    CustomerCreate,
    CustomerUpdate,
    ManualAssetCreate,
    ManualAssetUpdate,
    SiteCreate,
    SiteUpdate,
)


class FakeSession:
    def __init__(self, records: list[object] | None = None):
        self.records = {
            (type(record), record.id): record for record in (records or [])
        }
        self.deleted: list[object] = []

    def get(self, model, record_id):
        return self.records.get((model, record_id))

    def add(self, record):
        now = datetime.now(timezone.utc)
        if getattr(record, "id", None) is None:
            record.id = uuid.uuid4()
        if hasattr(record, "created_at") and getattr(record, "created_at", None) is None:
            record.created_at = now
        if hasattr(record, "updated_at") and getattr(record, "updated_at", None) is None:
            record.updated_at = now
        self.records[(type(record), record.id)] = record

    def delete(self, record):
        self.deleted.append(record)
        self.records.pop((type(record), record.id), None)

    def commit(self):
        pass

    def rollback(self):
        pass

    def refresh(self, record):
        pass


@pytest.fixture
def user() -> User:
    return User(id=uuid.uuid4(), email="admin@example.com", display_name="Admin", password_hash="unused")


@pytest.fixture
def workspace() -> Workspace:
    return Workspace(id=uuid.uuid4(), name="Atlas", slug="atlas")


def test_openapi_exposes_protected_crud_operations() -> None:
    paths = app.openapi()["paths"]
    detail_paths = {
        "/customers": "/customers/{customer_id}",
        "/sites": "/sites/{site_id}",
        "/manual-assets": "/manual-assets/{asset_id}",
    }
    for collection, detail_path in detail_paths.items():
        assert {"get", "post"} <= set(paths[collection])
        assert {"get", "patch", "delete"} <= set(paths[detail_path])


def test_customer_crud(workspace: Workspace, user: User) -> None:
    db = FakeSession([workspace])
    customer = create_customer(
        CustomerCreate(workspace_id=workspace.id, name="Kauri Health", description="Clinic"),
        user,
        db,
    )
    assert customer.workspace_id == workspace.id

    updated = update_customer(
        customer.id, CustomerUpdate(description="Community clinic"), user, db
    )
    assert updated.description == "Community clinic"
    assert delete_customer(customer.id, user, db).status_code == 204
    assert customer in db.deleted


def test_site_crud_requires_an_existing_customer(workspace: Workspace, user: User) -> None:
    customer = Customer(id=uuid.uuid4(), workspace_id=workspace.id, name="Customer")
    db = FakeSession([workspace, customer])
    site = create_site(
        SiteCreate(customer_id=customer.id, name="Auckland", address="Queen Street"),
        user,
        db,
    )
    assert site.customer_id == customer.id
    update_site(site.id, SiteUpdate(notes="Primary site"), user, db)
    assert site.notes == "Primary site"
    assert delete_site(site.id, user, db).status_code == 204

    with pytest.raises(HTTPException) as exc_info:
        create_site(
            SiteCreate(customer_id=uuid.uuid4(), name="Missing customer"), user, db
        )
    assert exc_info.value.status_code == 404


def test_manual_asset_crud_derives_workspace_and_rejects_cross_customer_site(
    workspace: Workspace, user: User
) -> None:
    customer = Customer(id=uuid.uuid4(), workspace_id=workspace.id, name="Customer")
    site = Site(id=uuid.uuid4(), customer_id=customer.id, name="Main site")
    db = FakeSession([workspace, customer, site])

    asset = create_manual_asset(
        ManualAssetCreate(
            customer_id=customer.id,
            site_id=site.id,
            name="core-switch-01",
            asset_type="network_switch",
            vendor="Aruba",
            metadata={"serial": "ABC123"},
        ),
        user,
        db,
    )
    assert asset.workspace_id == workspace.id
    assert asset.source_integration_id is None
    assert asset.external_id is None
    assert asset.metadata_ == {"serial": "ABC123"}

    update_manual_asset(
        asset.id, ManualAssetUpdate(status="stale", site_id=None), user, db
    )
    assert asset.status == "stale"
    assert asset.site_id is None
    assert delete_manual_asset(asset.id, user, db).status_code == 204

    other_customer = Customer(
        id=uuid.uuid4(), workspace_id=workspace.id, name="Other customer"
    )
    db.add(other_customer)
    with pytest.raises(HTTPException) as exc_info:
        create_manual_asset(
            ManualAssetCreate(
                customer_id=other_customer.id,
                site_id=site.id,
                name="invalid",
                asset_type="server",
            ),
            user,
            db,
        )
    assert exc_info.value.status_code == 404


def test_discovered_asset_cannot_be_changed_through_manual_asset_routes(
    workspace: Workspace,
) -> None:
    discovered = Asset(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        customer_id=uuid.uuid4(),
        source_integration_id=uuid.uuid4(),
        external_id="node/1",
        name="pve-01",
        asset_type="node",
        status="active",
        metadata_={},
    )
    db = FakeSession([discovered])
    with pytest.raises(HTTPException) as exc_info:
        get_manual_asset(db, discovered.id)
    assert exc_info.value.status_code == 404
