import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from app import services
from app.audit import add_audit_event
from app.authorization import Principal, ScopeGrant, get_principal
from app.database import get_db
from app.main import app
from app.models import (
    Asset,
    AssetCustomFieldValue,
    AssetType,
    AuditEvent,
    Customer,
    CustomFieldDefinition,
    Network,
    Permission,
    Role,
    Site,
    User,
)
from app.presenters import asset_response_data
from app.routes.asset_interfaces import _validate_network
from app.routes.custom_fields import (
    _definition_response,
    _validate_options,
    update_custom_field,
)
from app.routes.reference_data import (
    _asset_type_response,
    _validated_asset_type_keys,
    delete_asset_type,
)
from app.routes.assets import _available_asset_type
from app.routes.roles import _ensure_permissions_assignable
from app.routes.users import _ensure_target_manageable, _validate_assignments
from app.schemas import (
    AccessAssignmentInput,
    AssetTypeCreate,
    AssetTypeUpdate,
    CustomFieldDefinitionUpdate,
    CustomFieldOptionInput,
    ManualAssetCreate,
    RelationshipTypeCreate,
    RelationshipTypeUpdate,
)
from app.services import custom_fields as custom_field_service


def make_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email="admin@example.com",
        display_name="Admin",
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


def make_principal(*permissions: str) -> Principal:
    return Principal(
        make_user(),
        (
            ScopeGrant(
                assignment_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                role_name="Master Administrator",
                scope_type="global",
                customer_id=None,
                site_id=None,
                permissions=frozenset(permissions),
            ),
        ),
    )


def request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "DELETE",
            "path": "/test",
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
        }
    )


class Rows:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def all(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)


class AdminDatabase:
    def __init__(self, *, item=None, scalar_values=()):
        self.item = item
        self.scalar_values = list(scalar_values)
        self.added = []
        self.deleted = []

    def get(self, model, record_id):
        return self.item if self.item is not None and self.item.id == record_id else None

    def scalar(self, statement):
        if self.scalar_values:
            return self.scalar_values.pop(0)
        return self.item if isinstance(self.item, AssetType) else None

    def scalars(self, statement):
        return []

    def execute(self, statement):
        return Rows()

    def add(self, record):
        self.added.append(record)

    def delete(self, record):
        self.deleted.append(record)

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


def test_invalid_or_unsafe_icon_urls_are_rejected() -> None:
    with pytest.raises(ValidationError, match="HTTPS"):
        ManualAssetCreate(
            customer_id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            name="server",
            asset_type="server",
            icon_url="http://example.com/icon.png",
        )
    with pytest.raises(ValidationError, match="SVG"):
        AssetTypeCreate(
            key="server_custom",
            name="Server Custom",
            default_icon_url="https://example.com/icon.svg?version=1",
        )


def test_type_names_and_required_labels_are_trimmed_and_cannot_be_blank() -> None:
    assert AssetTypeCreate(key="server_custom", name="  Server Custom  ").name == (
        "Server Custom"
    )
    assert AssetTypeUpdate(name="  Renamed Server  ").name == "Renamed Server"

    relationship = RelationshipTypeCreate(
        key="managed_by_custom",
        name="  Managed by  ",
        source_label="  Managed by  ",
        target_label="  Manages  ",
    )
    assert relationship.name == "Managed by"
    assert relationship.source_label == "Managed by"
    assert relationship.target_label == "Manages"
    assert RelationshipTypeUpdate(name="  Renamed  ").name == "Renamed"

    with pytest.raises(ValidationError, match="must not be blank"):
        AssetTypeCreate(key="blank_name", name="   ")
    with pytest.raises(ValidationError, match="must not be null"):
        AssetTypeUpdate(name=None)
    with pytest.raises(ValidationError, match="must not be blank"):
        RelationshipTypeCreate(
            key="blank_label",
            name="Blank label",
            source_label="   ",
            target_label="Target",
        )
    with pytest.raises(ValidationError, match="must not be null"):
        RelationshipTypeUpdate(source_label=None)


def test_asset_icon_resolution_override_then_type_then_generic() -> None:
    now = datetime.now(timezone.utc)
    asset_type = AssetType(
        id=uuid.uuid4(),
        key="server",
        name="Server",
        default_icon_url="https://example.com/type.png",
        system_defined=True,
        active=True,
        sort_order=1,
        created_at=now,
        updated_at=now,
    )
    asset = Asset(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        name="srv",
        asset_type="server",
        icon_url="https://example.com/asset.png",
        status="active",
        source="manual",
        metadata_={},
        created_at=now,
        updated_at=now,
    )
    db = AdminDatabase(item=asset_type)
    assert asset_response_data(db, asset)["resolved_icon_url"].startswith(f"/api/assets/{asset.id}/icon?v=")
    asset.icon_url = None
    assert asset_response_data(db, asset)["resolved_icon_url"] == asset_type.default_icon_url
    asset_type.default_icon_url = None
    assert asset_response_data(db, asset)["resolved_icon_url"] is None


def test_system_and_used_asset_types_cannot_be_deleted() -> None:
    now = datetime.now(timezone.utc)
    system_type = AssetType(
        id=uuid.uuid4(), key="server", name="Server", system_defined=True,
        active=True, sort_order=1, created_at=now, updated_at=now,
    )
    with pytest.raises(HTTPException, match="System asset types"):
        delete_asset_type(
            system_type.id,
            request(),
            make_principal("asset_types.manage"),
            AdminDatabase(item=system_type),
        )
    custom_type = AssetType(
        id=uuid.uuid4(), key="custom_server", name="Custom Server",
        system_defined=False, active=True, sort_order=1, created_at=now, updated_at=now,
    )
    with pytest.raises(HTTPException, match="in use"):
        delete_asset_type(
            custom_type.id,
            request(),
            make_principal("asset_types.manage"),
            AdminDatabase(item=custom_type, scalar_values=[1, 0]),
        )


def test_inactive_asset_type_is_not_available_for_new_assets() -> None:
    inactive = AssetType(
        id=uuid.uuid4(), key="retired", name="Retired", system_defined=False,
        active=False, sort_order=1,
    )
    with pytest.raises(HTTPException, match="not active"):
        _available_asset_type(AdminDatabase(item=inactive), inactive.key)


def test_custom_field_ten_field_limit_counts_global_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definitions = [
        CustomFieldDefinition(
            id=uuid.uuid4(), key=f"field_{index}", name=f"Field {index}",
            data_type="text", required=False, active=True, sort_order=index,
            applies_to_all_asset_types=True,
        )
        for index in range(11)
    ]
    monkeypatch.setattr(
        custom_field_service,
        "applicable_definitions",
        lambda db, key, active_only=True: definitions,
    )

    class TypeKeys(AdminDatabase):
        def scalars(self, statement):
            return ["server"]

    with pytest.raises(HTTPException, match="At most 10"):
        custom_field_service.ensure_field_limit(TypeKeys())


def test_required_and_typed_custom_field_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = CustomFieldDefinition(
        id=uuid.uuid4(), key="rack", name="Rack", data_type="number",
        required=True, active=True, sort_order=1, applies_to_all_asset_types=True,
    )
    monkeypatch.setattr(
        custom_field_service,
        "applicable_definitions",
        lambda db, key, active_only=True: [definition],
    )
    asset = Asset(
        id=uuid.uuid4(), workspace_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        site_id=uuid.uuid4(), name="srv", asset_type="server", source="manual", metadata_={},
    )
    with pytest.raises(HTTPException, match="Required"):
        custom_field_service.set_asset_custom_fields(
            AdminDatabase(), asset, {}, replace_active=True
        )
    columns = custom_field_service._typed_columns(AdminDatabase(), definition, "12.5")
    assert columns["value_number"] == Decimal("12.5")
    with pytest.raises(HTTPException, match="number"):
        custom_field_service._typed_columns(AdminDatabase(), definition, "not-a-number")


@pytest.mark.parametrize("raw_value", ("NaN", "Infinity", "-Infinity"))
def test_numeric_custom_fields_reject_non_finite_values(raw_value: str) -> None:
    definition = CustomFieldDefinition(name="Rack", data_type="number")
    with pytest.raises(HTTPException, match="finite number") as exc_info:
        custom_field_service._typed_columns(AdminDatabase(), definition, raw_value)
    assert exc_info.value.status_code == 422


@pytest.mark.parametrize(
    ("raw_value", "message"),
    (
        ("10000000000000000", "16 digits before"),
        ("-10000000000000000", "16 digits before"),
        ("1e999999999", "16 digits before"),
        ("0.000000001", "8 digits after"),
    ),
)
def test_numeric_custom_fields_enforce_database_precision(
    raw_value: str, message: str
) -> None:
    definition = CustomFieldDefinition(name="Rack", data_type="number")
    with pytest.raises(HTTPException, match=message) as exc_info:
        custom_field_service._typed_columns(AdminDatabase(), definition, raw_value)
    assert exc_info.value.status_code == 422


def test_numeric_custom_fields_accept_database_boundaries() -> None:
    definition = CustomFieldDefinition(name="Rack", data_type="number")
    for raw_value in (
        "9999999999999999.99999999",
        "-9999999999999999.99999999",
        "1.230000000",
        "0e-999999999",
    ):
        columns = custom_field_service._typed_columns(
            AdminDatabase(), definition, raw_value
        )
        assert columns["value_number"] == Decimal(raw_value)


def test_deactivated_custom_field_values_remain_readable() -> None:
    definition = CustomFieldDefinition(
        id=uuid.uuid4(), key="legacy_note", name="Legacy note", data_type="text",
        required=False, active=False, sort_order=1, applies_to_all_asset_types=True,
    )
    stored = AssetCustomFieldValue(
        id=uuid.uuid4(), asset_id=uuid.uuid4(), field_definition_id=definition.id,
        value_text="preserved", value_number=None, value_date=None, value_bool=None,
        value_option_id=None,
    )

    class ValueDatabase(AdminDatabase):
        def execute(self, statement):
            return Rows([(stored, definition, None)])

    asset = Asset(id=stored.asset_id, asset_type="server")
    assert custom_field_service.custom_field_values(ValueDatabase(), asset) == {
        "legacy_note": "preserved"
    }


def test_audit_metadata_redacts_passwords_tokens_and_hashes() -> None:
    db = AdminDatabase()
    event = add_audit_event(
        db,
        action="user.updated",
        target_type="user",
        actor=make_user(),
        metadata={
            "password": "never-store-this",
            "nested": {"access_token": "secret-token", "safe": "visible"},
            "password_hash": "hash-value",
            "changed_at": datetime(2026, 7, 14, tzinfo=timezone.utc),
            "decimal": Decimal("12.5"),
        },
    )
    assert event.metadata_["password"] == "[redacted]"
    assert event.metadata_["nested"]["access_token"] == "[redacted]"
    assert event.metadata_["nested"]["safe"] == "visible"
    assert event.metadata_["changed_at"] == "2026-07-14T00:00:00+00:00"
    assert event.metadata_["decimal"] == "12.5"
    assert "never-store-this" not in str(event.metadata_)


def test_administrator_cannot_assign_or_define_master_only_permissions() -> None:
    actor = make_principal("users.assign_roles", "roles.manage")
    role = Role(
        id=uuid.uuid4(),
        name="Master-like",
        system_defined=False,
        active=True,
        sort_order=100,
    )

    class AssignmentDatabase(AdminDatabase):
        def get(self, model, record_id):
            if model is Role and record_id == role.id:
                return role
            return super().get(model, record_id)

        def scalars(self, statement):
            return ["users.assign_roles", "system_settings.manage"]

    assignment = AccessAssignmentInput(role_id=role.id, scope_type="global")
    with pytest.raises(HTTPException, match="permissions you do not hold"):
        _validate_assignments(AssignmentDatabase(), actor, [assignment])

    with pytest.raises(HTTPException, match="permissions you do not hold"):
        _ensure_permissions_assignable(
            actor,
            [
                Permission(
                    id=uuid.uuid4(),
                    key="system_settings.manage",
                    name="Manage settings",
                    system_defined=True,
                )
            ],
        )


def test_administrator_cannot_take_over_a_higher_privilege_account() -> None:
    actor = make_principal("users.edit")
    target = make_principal("users.edit", "system_settings.manage")
    with pytest.raises(HTTPException, match="permissions above your own"):
        _ensure_target_manageable(actor, target)


def test_changing_a_custom_field_to_dropdown_requires_options() -> None:
    definition = CustomFieldDefinition(
        id=uuid.uuid4(),
        key="rack",
        name="Rack",
        data_type="text",
        required=False,
        active=True,
        sort_order=1,
        applies_to_all_asset_types=True,
    )
    db = AdminDatabase(item=definition, scalar_values=[0, 0])
    with pytest.raises(HTTPException, match="require options"):
        update_custom_field(
            definition.id,
            CustomFieldDefinitionUpdate(data_type="dropdown"),
            request(),
            make_principal("custom_fields.manage"),
            db,
        )


def test_dropdown_options_must_be_unique_and_have_an_active_choice() -> None:
    duplicate = [
        CustomFieldOptionInput(value="one", label="One"),
        CustomFieldOptionInput(value="one", label="Duplicate"),
    ]
    with pytest.raises(HTTPException, match="unique"):
        _validate_options("dropdown", True, duplicate)
    inactive = [
        CustomFieldOptionInput(value="retired", label="Retired", active=False)
    ]
    with pytest.raises(HTTPException, match="active option"):
        _validate_options("dropdown", True, inactive)


def test_relationship_type_restrictions_reject_unknown_asset_types() -> None:
    with pytest.raises(HTTPException, match="Unknown allowed asset types"):
        _validated_asset_type_keys(AdminDatabase(), ["missing_type"])


def test_reference_usage_counts_are_filtered_to_the_principal_scope() -> None:
    customer_id = uuid.uuid4()
    site_id = uuid.uuid4()
    scoped = Principal(
        make_user(),
        (
            ScopeGrant(
                assignment_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                role_name="Viewer",
                scope_type="site",
                customer_id=customer_id,
                site_id=site_id,
                permissions=frozenset({"assets.view", "custom_fields.view"}),
            ),
        ),
    )

    class StatementDatabase(AdminDatabase):
        def __init__(self):
            super().__init__()
            self.statements = []

        def scalar(self, statement):
            self.statements.append(str(statement))
            return 0

        def scalars(self, statement):
            self.statements.append(str(statement))
            return []

    db = StatementDatabase()
    asset_type = AssetType(
        id=uuid.uuid4(),
        key="server",
        name="Server",
        system_defined=True,
        active=True,
        sort_order=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    definition = CustomFieldDefinition(
        id=uuid.uuid4(),
        key="rack",
        name="Rack",
        data_type="text",
        required=False,
        active=True,
        sort_order=1,
        applies_to_all_asset_types=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    _asset_type_response(db, asset_type, scoped)
    _definition_response(db, definition, scoped)
    scoped_queries = "\n".join(db.statements)
    assert "assets.customer_id =" in scoped_queries
    assert "assets.site_id =" in scoped_queries


def test_site_scoped_user_cannot_attach_a_hidden_customer_wide_network() -> None:
    customer_id = uuid.uuid4()
    site_id = uuid.uuid4()
    scoped = Principal(
        make_user(),
        (
            ScopeGrant(
                assignment_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                role_name="Site operator",
                scope_type="site",
                customer_id=customer_id,
                site_id=site_id,
                permissions=frozenset({"networks.create"}),
            ),
        ),
    )
    asset = Asset(id=uuid.uuid4(), customer_id=customer_id, site_id=site_id)
    network = Network(id=uuid.uuid4(), customer_id=customer_id, site_id=None)
    with pytest.raises(HTTPException) as exc_info:
        _validate_network(asset, network, scoped, "networks.create")
    assert exc_info.value.status_code == 404


def test_forced_change_account_can_only_bootstrap_its_slim_context() -> None:
    principal = make_principal("assets.view")
    principal.user.force_password_change = True
    customer = Customer(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        name="Home",
        description="Must not be returned by the slim selector",
        status="active",
    )
    site = Site(
        id=uuid.uuid4(),
        customer_id=customer.id,
        name="Homelab",
        address="Must not be returned",
        notes="Must not be returned",
        status="active",
    )

    class ContextDatabase(AdminDatabase):
        def scalars(self, statement):
            sql = str(statement)
            if "FROM customers" in sql:
                return [customer]
            if "FROM sites" in sql:
                return [site]
            return []

    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_db] = lambda: ContextDatabase()
    with TestClient(app) as client:
        response = client.get("/api/context")
        protected_response = client.get("/api/assets")
        session_probe_response = client.get("/api/protected")

    assert response.status_code == 200
    assert response.json() == {
        "customers": [
            {"id": str(customer.id), "name": "Home", "status": "active"}
        ],
        "sites": [
            {
                "id": str(site.id),
                "customer_id": str(customer.id),
                "name": "Homelab",
                "status": "active",
            }
        ],
        "global_access": True,
    }
    assert protected_response.status_code == 403
    assert session_probe_response.status_code == 403


def test_unauthorised_user_cannot_read_audit_log() -> None:
    viewer = make_principal("assets.view")
    app.dependency_overrides[get_principal] = lambda: viewer
    app.dependency_overrides[get_db] = lambda: AdminDatabase()
    with TestClient(app) as client:
        response = client.get("/api/audit-events")
    assert response.status_code == 403


def test_viewer_cannot_edit_asset_custom_field_values() -> None:
    viewer = make_principal("assets.view", "custom_fields.view")
    app.dependency_overrides[get_principal] = lambda: viewer
    app.dependency_overrides[get_db] = lambda: AdminDatabase()
    with TestClient(app) as client:
        response = client.put(
            f"/api/assets/{uuid.uuid4()}/custom-fields",
            json={"values": {"rack": 12}},
        )
    assert response.status_code == 403
