import uuid
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException

from app.main import app
from app.models import Asset, AssetInterface, AssetRelationship, Customer, Network, Site, User, Workspace
from app.routes.asset_interfaces import create_asset_interface, update_asset_interface
from app.routes.asset_relationships import (
    create_asset_relationship,
    delete_asset_relationship,
    list_asset_relationships,
)
from app.routes.assets import create_asset, get_asset, list_assets, update_asset
from app.routes.networks import create_network, update_network
from app.routes.customers import create_customer, delete_customer, update_customer
from app.routes.manual_assets import (
    create_manual_asset,
    delete_manual_asset,
    get_manual_asset,
    update_manual_asset,
)
from app.routes.sites import create_site, delete_site, update_site
from app.routes.topology import get_topology
from app.schemas import (
    CustomerCreate,
    CustomerUpdate,
    ManualAssetCreate,
    ManualAssetUpdate,
    AssetRelationshipCreate,
    AssetInterfaceCreate,
    AssetInterfaceUpdate,
    NetworkCreate,
    NetworkUpdate,
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

    def scalar(self, statement):
        model = statement.column_descriptions[0].get("entity")
        return next((record for (record_type, _), record in self.records.items() if record_type is model), None)

    def scalars(self, statement):
        model = statement.column_descriptions[0].get("entity")
        return [record for (record_type, _), record in self.records.items() if record_type is model]

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
        "/assets": "/assets/{asset_id}",
    }
    for collection, detail_path in detail_paths.items():
        assert {"get", "post"} <= set(paths[collection])
        assert {"get", "patch", "delete"} <= set(paths[detail_path])
    assert {"get", "post"} <= set(paths["/asset-relationships"])
    assert "delete" in paths["/asset-relationships/{relationship_id}"]
    assert {"get", "post"} <= set(paths["/networks"])
    assert {"get", "patch", "delete"} <= set(paths["/networks/{network_id}"])
    assert {"get", "post"} <= set(paths["/asset-interfaces"])
    assert {"patch", "delete"} <= set(paths["/asset-interfaces/{interface_id}"])


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


def test_asset_and_relationship_create_list_get_update_flows(
    workspace: Workspace, user: User
) -> None:
    customer = Customer(id=uuid.uuid4(), workspace_id=workspace.id, name="Customer")
    site = Site(id=uuid.uuid4(), customer_id=customer.id, name="Main")
    db = FakeSession([workspace, customer, site])

    first = create_asset(
        ManualAssetCreate(
            customer_id=customer.id,
            site_id=site.id,
            name="router-01",
            asset_type="router",
            hostname="router-01.example.test",
            ip_address="192.0.2.10",
        ),
        user,
        db,
    )
    second = create_asset(
        ManualAssetCreate(customer_id=customer.id, name="switch-01", asset_type="switch"),
        user,
        db,
    )
    assert second.ip_address is None
    assert get_asset(first.id, user, db) is first
    assert len(list_assets(user, None, None, 100, 0, db)) == 2
    update_asset(first.id, ManualAssetUpdate(model="Atlas Edge"), user, db)
    assert first.model == "Atlas Edge"

    edge = create_asset_relationship(
        AssetRelationshipCreate(
            source_asset_id=first.id,
            target_asset_id=second.id,
            relationship_type="connects_to",
            notes="uplink",
        ),
        user,
        db,
    )
    assert edge["notes"] == "uplink"
    assert edge["source_asset_name"] == "router-01"
    assert edge["target_asset_name"] == "switch-01"
    assert len(list_asset_relationships(user, None, 500, 0, db)) == 1
    assert delete_asset_relationship(edge["id"], user, db).status_code == 204


def test_relationship_rejects_missing_assets(user: User) -> None:
    db = FakeSession()
    with pytest.raises(HTTPException) as exc_info:
        create_asset_relationship(
            AssetRelationshipCreate(
                source_asset_id=uuid.uuid4(),
                target_asset_id=uuid.uuid4(),
                relationship_type="depends_on",
            ),
            user,
            db,
        )
    assert exc_info.value.status_code == 404


def test_topology_returns_frontend_friendly_named_graph(
    workspace: Workspace, user: User
) -> None:
    customer = Customer(id=uuid.uuid4(), workspace_id=workspace.id, name="Home Lab")
    site = Site(id=uuid.uuid4(), customer_id=customer.id, name="Home")
    host = Asset(
        id=uuid.uuid4(), workspace_id=workspace.id, customer_id=customer.id,
        site_id=site.id, name="pve1", asset_type="proxmox_host", status="active",
        source="manual", metadata_={},
    )
    vm = Asset(
        id=uuid.uuid4(), workspace_id=workspace.id, customer_id=customer.id,
        site_id=site.id, name="docker01", asset_type="virtual_machine", status="active",
        source="manual", metadata_={},
    )
    edge = AssetRelationship(
        id=uuid.uuid4(), source_asset_id=vm.id, target_asset_id=host.id,
        relationship_type="runs_on", notes=None, metadata_={},
    )
    network = Network(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id, name="Apps VLAN",
        network_type="vlan", vlan_id=5, cidr="192.168.5.0/24",
    )
    interface = AssetInterface(
        id=uuid.uuid4(), asset_id=vm.id, network_id=network.id, name="eth0",
        ip_address="192.168.5.8", is_primary=True,
    )
    db = FakeSession([workspace, customer, site, host, vm, edge, network, interface])
    topology = get_topology(user, db)
    assert [item.name for item in topology["customers"]] == ["Home Lab"]
    assert len(topology["assets"]) == 2
    assert topology["relationships"][0]["source_asset_name"] == "docker01"
    assert topology["relationships"][0]["target_asset_name"] == "pve1"
    assert topology["networks"][0].name == "Apps VLAN"
    assert topology["asset_interfaces"][0].ip_address == "192.168.5.8"


def test_network_and_asset_interface_creation(
    workspace: Workspace, user: User
) -> None:
    customer = Customer(id=uuid.uuid4(), workspace_id=workspace.id, name="Home Lab")
    site = Site(id=uuid.uuid4(), customer_id=customer.id, name="Home")
    asset = Asset(
        id=uuid.uuid4(), workspace_id=workspace.id, customer_id=customer.id,
        site_id=site.id, name="docker01", asset_type="docker_host", status="active",
        source="manual", metadata_={},
    )
    db = FakeSession([workspace, customer, site, asset])
    network = create_network(
        NetworkCreate(
            customer_id=customer.id, site_id=site.id, name="Apps VLAN",
            network_type="vlan", vlan_id=5, cidr="192.168.5.1/24",
            gateway="192.168.5.1",
        ),
        user,
        db,
    )
    assert network.cidr == "192.168.5.0/24"
    interface = create_asset_interface(
        AssetInterfaceCreate(
            asset_id=asset.id, network_id=network.id, name="eth0",
            ip_address="192.168.5.8", mac_address="02:00:00:00:05:08", is_primary=True,
        ),
        user,
        db,
    )
    assert interface.network_id == network.id
    update_network(network.id, NetworkUpdate(purpose="Applications"), user, db)
    update_asset_interface(
        interface.id, AssetInterfaceUpdate(notes="Primary LAN"), user, db
    )
    assert network.purpose == "Applications"
    assert interface.notes == "Primary LAN"
