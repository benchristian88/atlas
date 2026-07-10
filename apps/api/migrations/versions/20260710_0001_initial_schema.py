"""Create the initial Atlas schema.

Revision ID: 20260710_0001
Revises:
Create Date: 2026-07-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260710_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def uuid_pk() -> sa.Column:
    return sa.Column(
        "id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )


def created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def updated_at() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def upgrade() -> None:
    op.create_table(
        "users",
        uuid_pk(),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        created_at(),
        updated_at(),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "workspaces",
        uuid_pk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        created_at(),
        updated_at(),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
    )
    op.create_table(
        "customers",
        uuid_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "workspace_id", "name", name="uq_customers_workspace_name"
        ),
    )
    op.create_index("ix_customers_workspace_id", "customers", ["workspace_id"])
    op.create_table(
        "sites",
        uuid_pk(),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text()),
        sa.Column("notes", sa.Text()),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("customer_id", "name", name="uq_sites_customer_name"),
    )
    op.create_index("ix_sites_customer_id", "sites", ["customer_id"])
    op.create_table(
        "integrations",
        uuid_pk(),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("plugin_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column("username_or_token_id", sa.String(255), nullable=False),
        sa.Column("secret_reference", sa.String(1024), nullable=False),
        sa.Column(
            "verify_tls", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
    )
    for column in ("customer_id", "site_id", "plugin_id", "status"):
        op.create_index(f"ix_integrations_{column}", "integrations", [column])

    op.create_table(
        "discovery_runs",
        uuid_pk(),
        sa.Column("integration_id", UUID, nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("raw_payload", JSONB),
        sa.Column("summary", JSONB),
        sa.ForeignKeyConstraint(
            ["integration_id"], ["integrations.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_discovery_runs_integration_id", "discovery_runs", ["integration_id"])
    op.create_index("ix_discovery_runs_status", "discovery_runs", ["status"])

    op.create_table(
        "assets",
        uuid_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("source_integration_id", UUID),
        sa.Column("external_id", sa.String(1024)),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(100), nullable=False),
        sa.Column("vendor", sa.String(100)),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("description", sa.Text()),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("first_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_integration_id"], ["integrations.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "source_integration_id",
            "external_id",
            name="uq_assets_source_external_id",
        ),
    )
    for column in (
        "workspace_id", "customer_id", "site_id", "source_integration_id",
        "asset_type", "vendor", "status", "last_seen_at",
    ):
        op.create_index(f"ix_assets_{column}", "assets", [column])
    op.create_index("ix_assets_customer_type", "assets", ["customer_id", "asset_type"])

    op.create_table(
        "asset_relationships",
        uuid_pk(),
        sa.Column("source_asset_id", UUID, nullable=False),
        sa.Column("target_asset_id", UUID, nullable=False),
        sa.Column("relationship_type", sa.String(100), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(["source_asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "source_asset_id", "target_asset_id", "relationship_type",
            name="uq_asset_relationships_edge_type",
        ),
    )
    for column in ("source_asset_id", "target_asset_id", "relationship_type"):
        op.create_index(
            f"ix_asset_relationships_{column}", "asset_relationships", [column]
        )

    op.create_table(
        "asset_facts",
        uuid_pk(),
        sa.Column("asset_id", UUID, nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", JSONB, nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("asset_id", "key", "source", name="uq_asset_facts_key_source"),
    )
    op.create_index("ix_asset_facts_asset_id", "asset_facts", ["asset_id"])

    op.create_table(
        "documents",
        uuid_pk(),
        sa.Column("asset_id", UUID, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("generated_from_discovery_run_id", UUID),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["generated_from_discovery_run_id"],
            ["discovery_runs.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_documents_asset_id", "documents", ["asset_id"])
    op.create_index(
        "ix_documents_generated_from_discovery_run_id",
        "documents",
        ["generated_from_discovery_run_id"],
    )

    op.create_table(
        "audit_events",
        uuid_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("user_id", UUID),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", UUID),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        created_at(),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("workspace_id", "user_id", "event_type", "target_id", "created_at"):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])


def downgrade() -> None:
    for table in (
        "audit_events",
        "documents",
        "asset_facts",
        "asset_relationships",
        "assets",
        "discovery_runs",
        "integrations",
        "sites",
        "customers",
        "workspaces",
        "users",
    ):
        op.drop_table(table)
