"""Add authentication, scoped RBAC, reference data and enrichment foundations.

Revision ID: 20260714_0004
Revises: 20260714_0003
Create Date: 2026-07-14

Legacy data is preserved deliberately. Assets without a valid site receive a
per-customer ``Default Site``. Relationship context is copied from the source
asset; pre-existing cross-context edges are retained and marked rather than
being deleted or made impossible to migrate. New writes are context-validated
by the application layer.
"""

from collections.abc import Sequence

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0004"
down_revision: str | None = "20260714_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


PERMISSIONS: dict[str, tuple[str, str]] = {
    "users.view": ("View users", "Users"),
    "users.create": ("Create users", "Users"),
    "users.edit": ("Edit users", "Users"),
    "users.disable": ("Enable or disable users", "Users"),
    "users.assign_roles": ("Assign roles and access scopes", "Users"),
    "roles.view": ("View roles and permissions", "Roles"),
    "roles.manage": ("Manage roles and permissions", "Roles"),
    "customers.view": ("View customers", "Customers"),
    "customers.manage": ("Manage customers", "Customers"),
    "sites.view": ("View sites", "Sites"),
    "sites.manage": ("Manage sites", "Sites"),
    "assets.view": ("View assets", "Assets"),
    "assets.create": ("Create assets", "Assets"),
    "assets.edit": ("Edit assets", "Assets"),
    "assets.delete": ("Delete assets", "Assets"),
    "relationships.view": ("View relationships", "Relationships"),
    "relationships.create": ("Create relationships", "Relationships"),
    "relationships.edit": ("Edit relationships", "Relationships"),
    "relationships.delete": ("Delete relationships", "Relationships"),
    "networks.view": ("View networks and interfaces", "Networks"),
    "networks.create": ("Create networks and interfaces", "Networks"),
    "networks.edit": ("Edit networks and interfaces", "Networks"),
    "networks.delete": ("Delete networks and interfaces", "Networks"),
    "asset_types.view": ("View asset types", "Reference data"),
    "asset_types.manage": ("Manage asset types", "Reference data"),
    "relationship_types.view": ("View relationship types", "Reference data"),
    "relationship_types.manage": ("Manage relationship types", "Reference data"),
    "custom_fields.view": ("View custom-field definitions", "Reference data"),
    "custom_fields.manage": ("Manage custom-field definitions", "Reference data"),
    "audit.view": ("View audit events", "Audit"),
    "integrations.view": ("View integrations and discovery runs", "Integrations"),
    "integrations.manage": ("Manage integrations and discovery runs", "Integrations"),
    "system_settings.manage": ("Manage system settings", "System"),
}

MASTER_ADMINISTRATOR = "Master Administrator"
ADMINISTRATOR = "Administrator"
CUSTOMER_ADMINISTRATOR = "Customer Administrator"
VIEWER = "Viewer"

ROLE_PERMISSION_KEYS: dict[str, set[str]] = {
    MASTER_ADMINISTRATOR: set(PERMISSIONS),
    ADMINISTRATOR: {
        key
        for key in PERMISSIONS
        if key not in {"roles.manage", "system_settings.manage"}
    },
    CUSTOMER_ADMINISTRATOR: {
        "customers.view",
        "customers.manage",
        "sites.view",
        "sites.manage",
        "assets.view",
        "assets.create",
        "assets.edit",
        "assets.delete",
        "relationships.view",
        "relationships.create",
        "relationships.edit",
        "relationships.delete",
        "networks.view",
        "networks.create",
        "networks.edit",
        "networks.delete",
        "asset_types.view",
        "relationship_types.view",
        "custom_fields.view",
        "integrations.view",
        "integrations.manage",
    },
    VIEWER: {
        "customers.view",
        "sites.view",
        "assets.view",
        "relationships.view",
        "networks.view",
        "asset_types.view",
        "relationship_types.view",
        "custom_fields.view",
        "integrations.view",
    },
}

ASSET_TYPES: tuple[tuple[str, str, str], ...] = (
    ("unknown", "Unknown", "Other"),
    ("firewall", "Firewall", "Network"),
    ("router", "Router", "Network"),
    ("switch", "Switch", "Network"),
    ("network_switch", "Network Switch", "Network"),
    ("access_point", "Access Point", "Network"),
    ("network", "Network", "Network"),
    ("network_bridge", "Network Bridge", "Network"),
    ("vlan", "VLAN", "Network"),
    ("proxmox_cluster", "Proxmox Cluster", "Compute"),
    ("proxmox_host", "Proxmox Host", "Compute"),
    ("hypervisor_node", "Hypervisor Node", "Compute"),
    ("node", "Node", "Compute"),
    ("server", "Server", "Compute"),
    ("physical_server", "Physical Server", "Compute"),
    ("virtual_machine", "Virtual Machine", "Compute"),
    ("container", "Container", "Compute"),
    ("lxc_container", "LXC Container", "Compute"),
    ("docker_host", "Docker Host", "Compute"),
    ("docker_container", "Docker Container", "Compute"),
    ("application", "Application", "Software"),
    ("service", "Service", "Software"),
    ("proxy", "Proxy", "Software"),
    ("database", "Database", "Data"),
    ("storage_pool", "Storage Pool", "Storage"),
    ("nas", "NAS", "Storage"),
    ("backup_target", "Backup Target", "Backup"),
    ("backup_job", "Backup Job", "Backup"),
)

RELATIONSHIP_TYPES: tuple[tuple[str, str, str | None], ...] = (
    ("related_to", "Related to", "Related to"),
    ("contains", "Contains", "Contained by"),
    ("hosts", "Hosts", "Hosted on"),
    ("hosted_on", "Hosted on", "Hosts"),
    ("runs_on", "Runs on", "Runs"),
    ("runs", "Runs", "Runs on"),
    ("connects_to", "Connects to", "Connects to"),
    ("connected_to", "Connected to", "Connected to"),
    ("routes", "Routes", "Routed by"),
    ("protects", "Protects", "Protected by"),
    ("protected_by", "Protected by", "Protects"),
    ("depends_on", "Depends on", "Required by"),
    ("uses_storage", "Uses storage", "Storage for"),
    ("backs_up_to", "Backs up to", "Backup destination for"),
    ("backed_up_by", "Backed up by", "Backs up"),
    ("monitors", "Monitors", "Monitored by"),
    ("proxies", "Proxies", "Proxied by"),
    ("authenticates", "Authenticates", "Authenticated by"),
    ("exposes", "Exposes", "Exposed by"),
    ("belongs_to_network", "Belongs to network", "Contains network member"),
    ("uplinks_to", "Uplinks to", "Downlinks to"),
    ("member_of", "Member of", "Has member"),
    ("connected_via", "Connected via", "Connects"),
    ("served_by", "Served by", "Provides service to"),
    ("provides_service_to", "Provides service to", "Served by"),
    ("managed_by", "Managed by", "Manages"),
    ("replicates_to", "Replicates to", "Replicated from"),
    ("syncs_to", "Syncs to", "Synced from"),
)


def uuid_pk() -> sa.Column:
    return sa.Column(
        "id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def drop_foreign_keys(table_name: str, constrained_columns: tuple[str, ...]) -> None:
    """Drop all reflected FKs over exactly these columns.

    Early Atlas migrations allowed PostgreSQL to derive some constraint names,
    while metadata naming conventions supplied names in other environments.
    Reflection makes this revision safe for either history.
    """

    if context.is_offline_mode():
        # Reflection is unavailable for ``alembic upgrade --sql``. These are
        # the deterministic names emitted by Atlas's earlier migrations; live
        # upgrades still reflect so installations with convention-derived
        # variants remain supported.
        legacy_names = {
            ("assets", ("site_id",)): "fk_assets_site_id_sites",
            ("integrations", ("site_id",)): "fk_integrations_site_id_sites",
            ("networks", ("site_id",)): "fk_networks_site_id_sites",
            (
                "asset_relationships",
                ("source_asset_id",),
            ): "fk_asset_relationships_source_asset_id_assets",
            (
                "asset_relationships",
                ("target_asset_id",),
            ): "fk_asset_relationships_target_asset_id_assets",
        }
        constraint_name = legacy_names.get((table_name, constrained_columns))
        if constraint_name is None:
            raise RuntimeError(
                f"No offline foreign-key name is known for {table_name}{constrained_columns}"
            )
        op.drop_constraint(
            constraint_name,
            table_name,
            type_="foreignkey",
        )
        return

    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if tuple(foreign_key["constrained_columns"]) == constrained_columns:
            op.drop_constraint(foreign_key["name"], table_name, type_="foreignkey")


def seed_rbac() -> None:
    permission_table = sa.table(
        "permissions",
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("category", sa.String()),
        sa.column("system_defined", sa.Boolean()),
    )
    rows = [
        {
            "key": key,
            "name": name,
            "description": f"Built-in {name.lower()} permission.",
            "category": category,
            "system_defined": True,
        }
        for key, (name, category) in PERMISSIONS.items()
    ]
    op.execute(
        postgresql.insert(permission_table)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["key"])
    )

    role_table = sa.table(
        "roles",
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("system_defined", sa.Boolean()),
        sa.column("active", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
    )
    role_rows = [
        {
            "name": name,
            "description": description,
            "system_defined": True,
            "active": True,
            "sort_order": sort_order,
        }
        for sort_order, (name, description) in enumerate(
            (
                (MASTER_ADMINISTRATOR, "Unrestricted global Atlas access."),
                (ADMINISTRATOR, "Administrative access except protected system controls."),
                (CUSTOMER_ADMINISTRATOR, "Administrative access within assigned contexts."),
                (VIEWER, "Read-only access within assigned contexts."),
            ),
            start=10,
        )
    ]
    op.execute(
        postgresql.insert(role_table)
        .values(role_rows)
        .on_conflict_do_nothing(index_elements=["name"])
    )

    mapping_statement = sa.text(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id
        FROM roles, permissions
        WHERE roles.name = :role_name AND permissions.key = :permission_key
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )
    bind = op.get_bind()
    for role_name, permission_keys in ROLE_PERMISSION_KEYS.items():
        for permission_key in sorted(permission_keys):
            bind.execute(
                mapping_statement,
                {"role_name": role_name, "permission_key": permission_key},
            )


def seed_taxonomy() -> None:
    asset_type_table = sa.table(
        "asset_types",
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("category", sa.String()),
        sa.column("system_defined", sa.Boolean()),
        sa.column("active", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
    )
    asset_rows = [
        {
            "key": key,
            "name": name,
            "description": f"Built-in {name} asset type.",
            "category": category,
            "system_defined": True,
            "active": True,
            "sort_order": sort_order,
        }
        for sort_order, (key, name, category) in enumerate(ASSET_TYPES, start=10)
    ]
    op.execute(
        postgresql.insert(asset_type_table)
        .values(asset_rows)
        .on_conflict_do_nothing(index_elements=["key"])
    )
    # Any plugin- or operator-defined legacy strings become managed definitions
    # before the foreign key is installed. No existing asset changes type.
    op.execute(
        """
        INSERT INTO asset_types
            (key, name, description, category, system_defined, active, sort_order)
        SELECT DISTINCT
            assets.asset_type,
            initcap(replace(assets.asset_type, '_', ' '))
                || ' [' || substr(md5(assets.asset_type), 1, 8) || ']',
            'Migrated from an existing asset type value.',
            'Migrated',
            false,
            true,
            1000
        FROM assets
        WHERE assets.asset_type IS NOT NULL AND btrim(assets.asset_type) <> ''
        ON CONFLICT (key) DO NOTHING
        """
    )

    relationship_type_table = sa.table(
        "relationship_types",
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("source_label", sa.String()),
        sa.column("target_label", sa.String()),
        sa.column("inverse_label", sa.String()),
        sa.column("directional", sa.Boolean()),
        sa.column("system_defined", sa.Boolean()),
        sa.column("active", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
    )
    relationship_rows = [
        {
            "key": key,
            "name": name,
            "description": f"Built-in {name.lower()} relationship type.",
            "source_label": name,
            "target_label": inverse_label or name,
            "inverse_label": inverse_label,
            "directional": name.lower() != (inverse_label or "").lower(),
            "system_defined": True,
            "active": True,
            "sort_order": sort_order,
        }
        for sort_order, (key, name, inverse_label) in enumerate(
            RELATIONSHIP_TYPES, start=10
        )
    ]
    op.execute(
        postgresql.insert(relationship_type_table)
        .values(relationship_rows)
        .on_conflict_do_nothing(index_elements=["key"])
    )
    op.execute(
        """
        INSERT INTO relationship_types
            (key, name, description, source_label, target_label, inverse_label,
             directional, system_defined, active, sort_order)
        SELECT DISTINCT
            asset_relationships.relationship_type,
            initcap(replace(asset_relationships.relationship_type, '_', ' '))
                || ' [' || substr(md5(asset_relationships.relationship_type), 1, 8) || ']',
            'Migrated from an existing relationship type value.',
            initcap(replace(asset_relationships.relationship_type, '_', ' ')),
            initcap(replace(asset_relationships.relationship_type, '_', ' ')),
            NULL,
            true,
            false,
            true,
            1000
        FROM asset_relationships
        WHERE asset_relationships.relationship_type IS NOT NULL
          AND btrim(asset_relationships.relationship_type) <> ''
        ON CONFLICT (key) DO NOTHING
        """
    )


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "users",
        sa.Column(
            "force_password_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.add_column(
        "users",
        sa.Column(
            "failed_login_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True)))
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "users",
        sa.Column(
            "auth_provider", sa.String(50), nullable=False, server_default="local"
        ),
    )
    op.add_column("users", sa.Column("external_subject", sa.String(255)))
    op.add_column(
        "users",
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_users_is_active", "users", ["is_active"])
    op.create_index("ix_users_auth_provider", "users", ["auth_provider"])
    op.create_unique_constraint(
        "uq_users_auth_provider_external_subject",
        "users",
        ["auth_provider", "external_subject"],
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT lower(btrim(email))
                FROM users
                GROUP BY lower(btrim(email))
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Atlas cannot normalize duplicate case-insensitive user emails';
            END IF;
        END $$
        """
    )
    op.execute("UPDATE users SET email = lower(btrim(email))")
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )

    op.create_unique_constraint(
        "uq_sites_customer_id_id", "sites", ["customer_id", "id"]
    )

    op.create_table(
        "roles",
        uuid_pk(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "system_defined", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *timestamps(),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )
    op.create_index("ix_roles_active", "roles", ["active"])
    op.create_table(
        "permissions",
        uuid_pk(),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(100)),
        sa.Column(
            "system_defined", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        *timestamps(),
        sa.UniqueConstraint("key", name="uq_permissions_key"),
    )
    op.create_index("ix_permissions_category", "permissions", ["category"])
    op.create_table(
        "role_permissions",
        sa.Column("role_id", UUID, nullable=False),
        sa.Column("permission_id", UUID, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permissions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )
    op.create_table(
        "access_assignments",
        uuid_pk(),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("role_id", UUID, nullable=False),
        sa.Column("scope_type", sa.String(20), nullable=False),
        sa.Column("customer_id", UUID),
        sa.Column("site_id", UUID),
        *timestamps(),
        sa.CheckConstraint(
            "(scope_type = 'global' AND customer_id IS NULL AND site_id IS NULL) OR "
            "(scope_type = 'customer' AND customer_id IS NOT NULL AND site_id IS NULL) OR "
            "(scope_type = 'site' AND customer_id IS NOT NULL AND site_id IS NOT NULL)",
            name=op.f("ck_access_assignments_valid_scope"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_access_assignments_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )
    for column in ("user_id", "role_id", "scope_type", "customer_id", "site_id"):
        op.create_index(
            f"ix_access_assignments_{column}", "access_assignments", [column]
        )
    op.create_index(
        "uq_access_assignments_global",
        "access_assignments",
        ["user_id", "role_id"],
        unique=True,
        postgresql_where=sa.text("scope_type = 'global'"),
    )
    op.create_index(
        "uq_access_assignments_customer",
        "access_assignments",
        ["user_id", "role_id", "customer_id"],
        unique=True,
        postgresql_where=sa.text("scope_type = 'customer'"),
    )
    op.create_index(
        "uq_access_assignments_site",
        "access_assignments",
        ["user_id", "role_id", "site_id"],
        unique=True,
        postgresql_where=sa.text("scope_type = 'site'"),
    )

    seed_rbac()
    # Before RBAC, every database user had the application's full global write
    # capability. Preserve that access during the transition.
    op.execute(
        """
        INSERT INTO access_assignments (user_id, role_id, scope_type)
        SELECT users.id, roles.id, 'global'
        FROM users
        JOIN roles ON roles.name = 'Master Administrator'
        ON CONFLICT DO NOTHING
        """
    )

    op.create_table(
        "asset_types",
        uuid_pk(),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(100)),
        sa.Column("default_icon_url", sa.String(2048)),
        sa.Column(
            "system_defined", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *timestamps(),
        sa.UniqueConstraint("name", name="uq_asset_types_name"),
    )
    op.create_index("ix_asset_types_key", "asset_types", ["key"], unique=True)
    op.create_index("ix_asset_types_category", "asset_types", ["category"])
    op.create_index("ix_asset_types_active", "asset_types", ["active"])
    op.create_index("ix_asset_types_sort_order", "asset_types", ["sort_order"])
    op.create_index(
        "uq_asset_types_name_lower",
        "asset_types",
        [sa.text("lower(name)")],
        unique=True,
    )
    op.create_table(
        "relationship_types",
        uuid_pk(),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("source_label", sa.String(255), nullable=False),
        sa.Column("target_label", sa.String(255), nullable=False),
        sa.Column("inverse_label", sa.String(255)),
        sa.Column(
            "directional", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "system_defined", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "allowed_source_asset_type_keys",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "allowed_target_asset_type_keys",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        *timestamps(),
        sa.UniqueConstraint("name", name="uq_relationship_types_name"),
    )
    op.create_index(
        "ix_relationship_types_key", "relationship_types", ["key"], unique=True
    )
    op.create_index("ix_relationship_types_active", "relationship_types", ["active"])
    op.create_index(
        "ix_relationship_types_sort_order", "relationship_types", ["sort_order"]
    )
    op.create_index(
        "uq_relationship_types_name_lower",
        "relationship_types",
        [sa.text("lower(name)")],
        unique=True,
    )
    op.execute(
        "UPDATE assets SET asset_type = 'unknown' "
        "WHERE asset_type IS NULL OR btrim(asset_type) = ''"
    )
    op.execute(
        "UPDATE asset_relationships SET relationship_type = 'related_to' "
        "WHERE relationship_type IS NULL OR btrim(relationship_type) = ''"
    )
    seed_taxonomy()

    op.add_column("assets", sa.Column("icon_url", sa.String(2048)))
    # Repair both absent sites and any pre-existing customer/site mismatch.
    # A deterministic name lets a retry reuse the same context safely.
    op.execute(
        """
        INSERT INTO sites (id, customer_id, name, status, created_at, updated_at)
        SELECT gen_random_uuid(), customers.id, 'Default Site', 'active', now(), now()
        FROM customers
        WHERE (
            EXISTS (
                SELECT 1
                FROM assets
                LEFT JOIN sites AS current_site ON current_site.id = assets.site_id
                WHERE assets.customer_id = customers.id
                  AND (
                      assets.site_id IS NULL
                      OR current_site.id IS NULL
                      OR current_site.customer_id <> assets.customer_id
                  )
            )
            OR EXISTS (
                SELECT 1
                FROM integrations
                LEFT JOIN sites AS current_site
                    ON current_site.id = integrations.site_id
                WHERE integrations.customer_id = customers.id
                  AND (
                      integrations.site_id IS NULL
                      OR current_site.id IS NULL
                      OR current_site.customer_id <> integrations.customer_id
                  )
            )
        )
          AND NOT EXISTS (
              SELECT 1 FROM sites AS default_site
              WHERE default_site.customer_id = customers.id
                AND default_site.name = 'Default Site'
          )
        ON CONFLICT (customer_id, name) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE assets
        SET site_id = default_site.id,
            updated_at = now()
        FROM sites AS default_site
        WHERE default_site.customer_id = assets.customer_id
          AND default_site.name = 'Default Site'
          AND (
              assets.site_id IS NULL
              OR NOT EXISTS (
                  SELECT 1
                  FROM sites AS current_site
                  WHERE current_site.id = assets.site_id
                    AND current_site.customer_id = assets.customer_id
              )
          )
        """
    )
    op.execute(
        """
        UPDATE integrations
        SET site_id = default_site.id,
            updated_at = now()
        FROM sites AS default_site
        WHERE default_site.customer_id = integrations.customer_id
          AND default_site.name = 'Default Site'
          AND (
              integrations.site_id IS NULL
              OR NOT EXISTS (
                  SELECT 1
                  FROM sites AS current_site
                  WHERE current_site.id = integrations.site_id
                    AND current_site.customer_id = integrations.customer_id
              )
          )
        """
    )
    op.execute(
        """
        UPDATE sites
        SET status = 'active', updated_at = now()
        WHERE name = 'Default Site'
          AND (
              EXISTS (
                  SELECT 1 FROM assets
                  WHERE assets.site_id = sites.id
              )
              OR EXISTS (
                  SELECT 1 FROM integrations
                  WHERE integrations.site_id = sites.id
              )
          )
        """
    )
    drop_foreign_keys("assets", ("site_id",))
    op.alter_column("assets", "site_id", existing_type=UUID, nullable=False)
    op.create_foreign_key(
        "fk_assets_customer_site_sites",
        "assets",
        "sites",
        ["customer_id", "site_id"],
        ["customer_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_assets_id_customer_site", "assets", ["id", "customer_id", "site_id"]
    )
    op.create_foreign_key(
        "fk_assets_asset_type_asset_types",
        "assets",
        "asset_types",
        ["asset_type"],
        ["key"],
        ondelete="RESTRICT",
    )

    drop_foreign_keys("integrations", ("site_id",))
    op.alter_column("integrations", "site_id", existing_type=UUID, nullable=False)
    op.create_foreign_key(
        "fk_integrations_customer_site_sites",
        "integrations",
        "sites",
        ["customer_id", "site_id"],
        ["customer_id", "id"],
        ondelete="RESTRICT",
    )

    # A legacy network with a cross-customer or missing site becomes a
    # customer-wide network. This preserves the record without retaining an
    # invalid ownership edge; NULL remains a supported all-sites scope.
    op.execute(
        """
        UPDATE networks
        SET site_id = NULL, updated_at = now()
        WHERE site_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM sites
              WHERE sites.id = networks.site_id
                AND sites.customer_id = networks.customer_id
          )
        """
    )
    drop_foreign_keys("networks", ("site_id",))
    op.create_foreign_key(
        "fk_networks_customer_site_sites",
        "networks",
        "sites",
        ["customer_id", "site_id"],
        ["customer_id", "id"],
        ondelete="RESTRICT",
    )

    op.add_column("asset_relationships", sa.Column("customer_id", UUID))
    op.add_column("asset_relationships", sa.Column("site_id", UUID))
    op.add_column(
        "asset_relationships",
        sa.Column(
            "legacy_cross_context",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        """
        UPDATE asset_relationships AS relationship
        SET customer_id = source_asset.customer_id,
            site_id = source_asset.site_id,
            legacy_cross_context = (
                source_asset.customer_id <> target_asset.customer_id
                OR source_asset.site_id <> target_asset.site_id
            )
        FROM assets AS source_asset, assets AS target_asset
        WHERE source_asset.id = relationship.source_asset_id
          AND target_asset.id = relationship.target_asset_id
        """
    )
    op.alter_column(
        "asset_relationships", "customer_id", existing_type=UUID, nullable=False
    )
    op.alter_column(
        "asset_relationships", "site_id", existing_type=UUID, nullable=False
    )
    op.create_index(
        "ix_asset_relationships_customer_id", "asset_relationships", ["customer_id"]
    )
    op.create_index(
        "ix_asset_relationships_site_id", "asset_relationships", ["site_id"]
    )
    op.create_index(
        "ix_asset_relationships_legacy_cross_context",
        "asset_relationships",
        ["legacy_cross_context"],
    )
    # Do not install composite endpoint/context FKs: they would reject valid
    # migration of legacy cross-context edges. Simple RESTRICT endpoint FKs
    # preserve every edge while application validation prohibits new mismatches.
    # The relationship's own context still has a composite customer/site FK.
    drop_foreign_keys("asset_relationships", ("source_asset_id",))
    drop_foreign_keys("asset_relationships", ("target_asset_id",))
    op.create_foreign_key(
        "fk_asset_relationships_source_asset_id_assets",
        "asset_relationships",
        "assets",
        ["source_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_asset_relationships_target_asset_id_assets",
        "asset_relationships",
        "assets",
        ["target_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_asset_relationships_customer_id_customers",
        "asset_relationships",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_asset_relationships_customer_site_sites",
        "asset_relationships",
        "sites",
        ["customer_id", "site_id"],
        ["customer_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_asset_relationships_relationship_type_relationship_types",
        "asset_relationships",
        "relationship_types",
        ["relationship_type"],
        ["key"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "custom_field_definitions",
        uuid_pk(),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("help_text", sa.Text()),
        sa.Column("data_type", sa.String(30), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "applies_to_all_asset_types",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        *timestamps(),
        sa.CheckConstraint(
            "data_type IN ('text', 'multiline_text', 'number', 'date', "
            "'boolean', 'url', 'dropdown')",
            name=op.f("ck_custom_field_definitions_valid_data_type"),
        ),
        sa.UniqueConstraint("key", name="uq_custom_field_definitions_key"),
    )
    for column in ("data_type", "active", "sort_order"):
        op.create_index(
            f"ix_custom_field_definitions_{column}",
            "custom_field_definitions",
            [column],
        )
    op.create_table(
        "custom_field_asset_types",
        sa.Column("field_definition_id", UUID, nullable=False),
        sa.Column("asset_type_key", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["field_definition_id"],
            ["custom_field_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["asset_type_key"], ["asset_types.key"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("field_definition_id", "asset_type_key"),
    )
    op.create_table(
        "custom_field_options",
        uuid_pk(),
        sa.Column("field_definition_id", UUID, nullable=False),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["field_definition_id"],
            ["custom_field_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "field_definition_id", "value", name="uq_custom_field_options_value"
        ),
        sa.UniqueConstraint(
            "field_definition_id",
            "id",
            name="uq_custom_field_options_definition_id_id",
        ),
    )
    op.create_index(
        "ix_custom_field_options_field_definition_id",
        "custom_field_options",
        ["field_definition_id"],
    )
    op.create_index("ix_custom_field_options_active", "custom_field_options", ["active"])
    op.create_table(
        "asset_custom_field_values",
        uuid_pk(),
        sa.Column("asset_id", UUID, nullable=False),
        sa.Column("field_definition_id", UUID, nullable=False),
        sa.Column("value_text", sa.Text()),
        sa.Column("value_number", sa.Numeric(24, 8)),
        sa.Column("value_date", sa.Date()),
        sa.Column("value_bool", sa.Boolean()),
        sa.Column("value_option_id", UUID),
        *timestamps(),
        sa.CheckConstraint(
            "num_nonnulls(value_text, value_number, value_date, value_bool, "
            "value_option_id) = 1",
            name=op.f("ck_asset_custom_field_values_exactly_one_typed_value"),
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["field_definition_id"],
            ["custom_field_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["field_definition_id", "value_option_id"],
            ["custom_field_options.field_definition_id", "custom_field_options.id"],
            name="fk_asset_custom_field_values_definition_option",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "asset_id",
            "field_definition_id",
            name="uq_asset_custom_field_values_asset_definition",
        ),
    )
    for column in ("asset_id", "field_definition_id", "value_option_id"):
        op.create_index(
            f"ix_asset_custom_field_values_{column}",
            "asset_custom_field_values",
            [column],
        )

    op.alter_column("audit_events", "workspace_id", existing_type=UUID, nullable=True)
    op.add_column("audit_events", sa.Column("actor_email", sa.String(320)))
    op.add_column("audit_events", sa.Column("actor_display_name", sa.String(255)))
    op.add_column("audit_events", sa.Column("customer_id", UUID))
    op.add_column("audit_events", sa.Column("site_id", UUID))
    op.add_column(
        "audit_events",
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("audit_events", sa.Column("summary", sa.Text()))
    op.add_column("audit_events", sa.Column("source_ip", sa.String(45)))
    op.add_column("audit_events", sa.Column("request_id", sa.String(100)))
    op.create_foreign_key(
        "fk_audit_events_customer_id_customers",
        "audit_events",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_audit_events_site_id_sites",
        "audit_events",
        "sites",
        ["site_id"],
        ["id"],
        ondelete="SET NULL",
    )
    for column in (
        "actor_email",
        "customer_id",
        "site_id",
        "success",
        "source_ip",
        "request_id",
    ):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])

    op.create_table(
        "system_settings",
        uuid_pk(),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", JSONB, nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sensitive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by_user_id", UUID),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)
    op.create_index(
        "ix_system_settings_updated_by_user_id",
        "system_settings",
        ["updated_by_user_id"],
    )


def downgrade() -> None:
    op.drop_table("system_settings")

    for column in (
        "request_id",
        "source_ip",
        "success",
        "site_id",
        "customer_id",
        "actor_email",
    ):
        op.drop_index(f"ix_audit_events_{column}", table_name="audit_events")
    op.drop_constraint(
        "fk_audit_events_site_id_sites", "audit_events", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_audit_events_customer_id_customers", "audit_events", type_="foreignkey"
    )
    for column in (
        "request_id",
        "source_ip",
        "summary",
        "success",
        "site_id",
        "customer_id",
        "actor_display_name",
        "actor_email",
    ):
        op.drop_column("audit_events", column)
    # A failed-login event can legitimately lack workspace context. Leave the
    # legacy column nullable rather than deleting audit data during downgrade.

    op.drop_table("asset_custom_field_values")
    op.drop_table("custom_field_options")
    op.drop_table("custom_field_asset_types")
    op.drop_table("custom_field_definitions")

    op.drop_constraint(
        "fk_asset_relationships_relationship_type_relationship_types",
        "asset_relationships",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_asset_relationships_customer_site_sites",
        "asset_relationships",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_asset_relationships_customer_id_customers",
        "asset_relationships",
        type_="foreignkey",
    )
    drop_foreign_keys("asset_relationships", ("source_asset_id",))
    drop_foreign_keys("asset_relationships", ("target_asset_id",))
    op.create_foreign_key(
        "fk_asset_relationships_source_asset_id_assets",
        "asset_relationships",
        "assets",
        ["source_asset_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_asset_relationships_target_asset_id_assets",
        "asset_relationships",
        "assets",
        ["target_asset_id"],
        ["id"],
        ondelete="CASCADE",
    )
    for column in ("legacy_cross_context", "site_id", "customer_id"):
        op.drop_index(
            f"ix_asset_relationships_{column}", table_name="asset_relationships"
        )
        op.drop_column("asset_relationships", column)

    op.drop_constraint(
        "fk_assets_asset_type_asset_types", "assets", type_="foreignkey"
    )
    op.drop_constraint("uq_assets_id_customer_site", "assets", type_="unique")
    op.drop_constraint("fk_assets_customer_site_sites", "assets", type_="foreignkey")
    op.alter_column("assets", "site_id", existing_type=UUID, nullable=True)
    op.create_foreign_key(
        "fk_assets_site_id_sites",
        "assets",
        "sites",
        ["site_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("assets", "icon_url")

    op.drop_constraint(
        "fk_integrations_customer_site_sites",
        "integrations",
        type_="foreignkey",
    )
    op.alter_column("integrations", "site_id", existing_type=UUID, nullable=True)
    op.create_foreign_key(
        "fk_integrations_site_id_sites",
        "integrations",
        "sites",
        ["site_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "fk_networks_customer_site_sites",
        "networks",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_networks_site_id_sites",
        "networks",
        "sites",
        ["site_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_table("relationship_types")
    op.drop_table("asset_types")

    op.drop_table("access_assignments")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_constraint("uq_sites_customer_id_id", "sites", type_="unique")

    op.drop_constraint(
        "uq_users_auth_provider_external_subject", "users", type_="unique"
    )
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_index("ix_users_auth_provider", table_name="users")
    op.drop_index("ix_users_is_active", table_name="users")
    for column in (
        "mfa_enabled",
        "external_subject",
        "auth_provider",
        "session_version",
        "locked_until",
        "failed_login_count",
        "last_login_at",
        "force_password_change",
        "is_active",
    ):
        op.drop_column("users", column)
