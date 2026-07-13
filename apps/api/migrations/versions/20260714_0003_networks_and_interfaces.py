"""Add first-class networks and asset interfaces.

Revision ID: 20260714_0003
Revises: 20260714_0002
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0003"
down_revision: str | None = "20260714_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def uuid_pk() -> sa.Column:
    return sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()"))


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def upgrade() -> None:
    op.create_table(
        "networks",
        uuid_pk(),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("network_type", sa.String(50), nullable=False),
        sa.Column("vlan_id", sa.Integer()),
        sa.Column("cidr", sa.String(49)),
        sa.Column("gateway", sa.String(45)),
        sa.Column("purpose", sa.String(255)),
        sa.Column("zone", sa.String(100)),
        sa.Column("notes", sa.Text()),
        *timestamps(),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("customer_id", "site_id", "name", name="uq_networks_customer_site_name"),
    )
    for column in ("customer_id", "site_id", "network_type", "cidr", "zone"):
        op.create_index(f"ix_networks_{column}", "networks", [column])

    op.create_table(
        "asset_interfaces",
        uuid_pk(),
        sa.Column("asset_id", UUID, nullable=False),
        sa.Column("network_id", UUID),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("mac_address", sa.String(17)),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text()),
        *timestamps(),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["network_id"], ["networks.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("asset_id", "name", name="uq_asset_interfaces_asset_name"),
    )
    for column in ("asset_id", "network_id", "ip_address", "mac_address", "is_primary"):
        op.create_index(f"ix_asset_interfaces_{column}", "asset_interfaces", [column])


def downgrade() -> None:
    op.drop_table("asset_interfaces")
    op.drop_table("networks")
