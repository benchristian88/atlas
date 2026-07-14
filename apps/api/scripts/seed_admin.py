import os
import warnings
from collections.abc import Mapping
from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import SessionLocal
from app.models import (
    AccessAssignment,
    AssetType,
    Customer,
    Permission,
    RelationshipType,
    Role,
    RolePermission,
    Site,
    User,
    Workspace,
)
from app.permissions import (
    MASTER_ADMINISTRATOR,
    PERMISSIONS,
    ROLE_PERMISSION_KEYS,
)
from app.taxonomy import ASSET_TYPES, RELATIONSHIP_TYPES

BOOTSTRAP_VARIABLES = (
    "ATLAS_BOOTSTRAP_ADMIN_EMAIL",
    "ATLAS_BOOTSTRAP_ADMIN_PASSWORD",
    "ATLAS_BOOTSTRAP_ADMIN_NAME",
)
LEGACY_VARIABLES = (
    "ATLAS_ADMIN_EMAIL",
    "ATLAS_ADMIN_PASSWORD",
    "ATLAS_ADMIN_DISPLAY_NAME",
)

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


class AdminSeedError(ValueError):
    """Raised when explicitly supplied bootstrap configuration is invalid."""


@dataclass(frozen=True)
class BootstrapAdmin:
    email: str
    password: str
    display_name: str
    legacy_fallback: bool = False


def _configured_group(
    environment: Mapping[str, str], variable_names: tuple[str, str, str]
) -> tuple[str, str, str] | None:
    supplied = [bool(environment.get(name, "").strip()) for name in variable_names]
    if not any(supplied):
        return None
    missing = [name for name, present in zip(variable_names, supplied) if not present]
    if missing:
        raise AdminSeedError(
            "Incomplete bootstrap configuration; missing: " + ", ".join(missing)
        )
    return (
        environment[variable_names[0]],
        environment[variable_names[1]],
        environment[variable_names[2]],
    )


def _bootstrap_admin(environment: Mapping[str, str]) -> BootstrapAdmin | None:
    configured = _configured_group(environment, BOOTSTRAP_VARIABLES)
    legacy_fallback = False
    email_variable = BOOTSTRAP_VARIABLES[0]
    password_variable = BOOTSTRAP_VARIABLES[1]
    if configured is None:
        configured = _configured_group(environment, LEGACY_VARIABLES)
        if configured is None:
            return None
        legacy_fallback = True
        email_variable = LEGACY_VARIABLES[0]
        password_variable = LEGACY_VARIABLES[1]
        warnings.warn(
            "ATLAS_ADMIN_* is deprecated and was used only because the users table "
            "is empty; migrate to ATLAS_BOOTSTRAP_ADMIN_* and remove the password "
            "after first login.",
            RuntimeWarning,
            stacklevel=2,
        )

    raw_email, password, raw_display_name = configured
    try:
        email = validate_email(
            raw_email.strip(), check_deliverability=False
        ).normalized.lower()
    except EmailNotValidError as exc:
        raise AdminSeedError(f"{email_variable} must be a valid email address") from exc
    if len(password) < 12:
        raise AdminSeedError(
            f"{password_variable} must contain at least 12 characters"
        )
    if len(password) > 1024:
        raise AdminSeedError(
            f"{password_variable} must not exceed 1024 characters"
        )
    display_name = raw_display_name.strip()
    if not display_name:
        raise AdminSeedError("Bootstrap administrator name must not be empty")
    if len(display_name) > 255:
        raise AdminSeedError("Bootstrap administrator name must not exceed 255 characters")
    return BootstrapAdmin(
        email=email,
        password=password,
        display_name=display_name,
        legacy_fallback=legacy_fallback,
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


def seed_admin(db: Session, environment: Mapping[str, str]) -> bool:
    """Create the one-time master administrator for an empty users table.

    ``False`` is a safe no-op: either a user already exists or no bootstrap
    credentials were supplied. Existing users are checked before configuration
    is read, so stale environment variables can never reset an account.
    """

    if db.scalar(select(User.id).limit(1)) is not None:
        return False

    bootstrap = _bootstrap_admin(environment)
    if bootstrap is None:
        return False

    master_role = _ensure_rbac(db)
    _ensure_taxonomy(db)
    _ensure_home_context(db)

    user = User(
        email=bootstrap.email,
        display_name=bootstrap.display_name,
        password_hash=hash_password(bootstrap.password),
        is_active=True,
        force_password_change=True,
        auth_provider="local",
        mfa_enabled=False,
    )
    db.add(user)
    db.flush()
    db.add(
        AccessAssignment(
            user_id=user.id,
            role_id=master_role.id,
            scope_type="global",
            customer_id=None,
            site_id=None,
        )
    )
    db.flush()

    # Re-adding a persistent object is a harmless no-op for SQLAlchemy and keeps
    # the function straightforward to inspect in isolated mocked-session tests.
    db.add(user)
    return True


def main() -> None:
    try:
        with SessionLocal.begin() as db:
            created = seed_admin(db, os.environ)
    except AdminSeedError as exc:
        raise SystemExit(f"Admin seed failed: {exc}") from exc

    if created:
        configured_email = (
            os.environ.get("ATLAS_BOOTSTRAP_ADMIN_EMAIL")
            or os.environ.get("ATLAS_ADMIN_EMAIL")
            or "the configured account"
        )
        print(
            "Created Atlas bootstrap administrator "
            f"{configured_email.strip().lower()}. Remove the bootstrap password "
            "from the environment after first login."
        )
    else:
        print(
            "No Atlas bootstrap administrator created (a user already exists or "
            "bootstrap credentials were not supplied)."
        )


if __name__ == "__main__":
    main()
