"""Idempotent protected definitions; never creates users from environment values."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import AssetType, Customer, Permission, RelationshipType, Role, RolePermission, Site, Workspace
from app.permissions import MASTER_ADMINISTRATOR, PERMISSIONS, ROLE_PERMISSION_KEYS
from app.taxonomy import ASSET_TYPES, RELATIONSHIP_TYPES
from app.models import SystemSetting
from app.services.system_settings import SESSION_LIFETIME_KEY, SESSION_DESCRIPTION

ADDITIONAL_ASSET_TYPES = (
    "hypervisor_node",
    "container",
    "network_bridge",
    "server",
    "network_switch",
    "node",
)
ADDITIONAL_RELATIONSHIP_TYPES = (
    "connected_to",
    "hosted_on",
    "backed_up_by",
    "managed_by",
    "provides_service_to",
)


def _asset_category(key: str) -> str:
    if key in {
        "firewall",
        "router",
        "switch",
        "access_point",
        "network",
        "network_bridge",
        "vlan",
    }:
        return "Network"
    if key in {
        "storage_pool",
        "nas",
        "backup_target",
        "backup_job",
    }:
        return "Storage"
    if key in {"application", "database", "service", "proxy"}:
        return "Software"
    return "Compute"


def _ensure_rbac(db: Session) -> Role:
    permissions: dict[str, Permission] = {}
    for key, (name, category) in PERMISSIONS.items():
        permission = db.scalar(select(Permission).where(Permission.key == key))
        if permission is None:
            permission = Permission(
                key=key,
                name=name,
                description=f"Built-in {name.lower()} permission.",
                category=category,
                system_defined=True,
            )
            db.add(permission)
            db.flush()
        else:
            permission.system_defined = True
        permissions[key] = permission

    role_descriptions = {
        MASTER_ADMINISTRATOR: "Unrestricted global Atlas access.",
        "Administrator": "Administrative access except protected system controls.",
        "Customer Administrator": "Administrative access within assigned contexts.",
        "Viewer": "Read-only access within assigned contexts.",
    }
    roles: dict[str, Role] = {}
    for sort_order, (name, description) in enumerate(
        role_descriptions.items(), start=10
    ):
        role = db.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(
                name=name,
                description=description,
                system_defined=True,
                active=True,
                sort_order=sort_order,
            )
            db.add(role)
            db.flush()
        else:
            role.system_defined = True
            role.active = True
        roles[name] = role

    for role_name, permission_keys in ROLE_PERMISSION_KEYS.items():
        role = roles[role_name]
        for permission_key in permission_keys:
            permission = permissions[permission_key]
            mapping_exists = db.scalar(
                select(RolePermission.role_id).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == permission.id,
                )
            )
            if mapping_exists is None:
                db.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permission.id,
                    )
                )
    db.flush()
    return roles[MASTER_ADMINISTRATOR]


def _ensure_taxonomy(db: Session) -> None:
    all_asset_types = tuple(dict.fromkeys((*ASSET_TYPES, *ADDITIONAL_ASSET_TYPES)))
    for sort_order, key in enumerate(all_asset_types, start=10):
        asset_type = db.scalar(select(AssetType).where(AssetType.key == key))
        if asset_type is None:
            name = key.replace("_", " ").title()
            if key == "vlan":
                name = "VLAN"
            elif key == "nas":
                name = "NAS"
            asset_type = AssetType(
                key=key,
                name=name,
                description=f"Built-in {name} asset type.",
                category=_asset_category(key),
                system_defined=True,
                active=True,
                sort_order=sort_order,
            )
            db.add(asset_type)
            db.flush()
        else:
            asset_type.system_defined = True

    all_relationship_types = tuple(
        dict.fromkeys((*RELATIONSHIP_TYPES, *ADDITIONAL_RELATIONSHIP_TYPES))
    )
    for sort_order, key in enumerate(all_relationship_types, start=10):
        relationship_type = db.scalar(
            select(RelationshipType).where(RelationshipType.key == key)
        )
        if relationship_type is None:
            name = key.replace("_", " ").title()
            relationship_type = RelationshipType(
                key=key,
                name=name,
                description=f"Built-in {name.lower()} relationship type.",
                source_label=name,
                target_label=name,
                inverse_label=None,
                directional=True,
                system_defined=True,
                active=True,
                sort_order=sort_order,
            )
            db.add(relationship_type)
            db.flush()
        else:
            relationship_type.system_defined = True


def _ensure_home_context(db: Session) -> None:
    """Create Home/Homelab only for an otherwise context-free installation."""

    customer = db.scalar(select(Customer).order_by(Customer.created_at, Customer.id))
    if customer is not None:
        return

    workspace = db.scalar(
        select(Workspace).order_by(Workspace.created_at, Workspace.id)
    )
    if workspace is None:
        workspace = Workspace(name="Atlas", slug="atlas")
        db.add(workspace)
        db.flush()

    home = Customer(
        workspace_id=workspace.id,
        name="Home",
        description="Default context created during Atlas bootstrap.",
        status="active",
    )
    db.add(home)
    db.flush()
    db.add(
        Site(
            customer_id=home.id,
            name="Homelab",
            notes="Default site created during Atlas bootstrap.",
            status="active",
        )
    )
    db.flush()


def seed_system(db: Session) -> None:
    _ensure_rbac(db)
    _ensure_taxonomy(db)
    if db.scalar(select(SystemSetting).where(SystemSetting.key == SESSION_LIFETIME_KEY)) is None:
        db.add(SystemSetting(key=SESSION_LIFETIME_KEY, value_=480, description=SESSION_DESCRIPTION, sensitive=False))
    db.flush()


def main() -> None:
    with SessionLocal.begin() as db:
        seed_system(db)
    print("Atlas system definitions ready.")


if __name__ == "__main__":
    main()
