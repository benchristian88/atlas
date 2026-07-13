"""Add manual infrastructure MVP fields.

Revision ID: 20260714_0002
Revises: 20260710_0001
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0002"
down_revision: str | None = "20260710_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
    )
    op.create_index("ix_customers_status", "customers", ["status"])
    op.add_column(
        "sites",
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
    )
    op.create_index("ix_sites_status", "sites", ["status"])

    op.add_column("assets", sa.Column("model", sa.String(255)))
    op.add_column("assets", sa.Column("hostname", sa.String(255)))
    op.add_column("assets", sa.Column("ip_address", sa.String(45)))
    op.add_column(
        "assets",
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
    )
    op.execute(
        "UPDATE assets SET source = 'discovered' WHERE source_integration_id IS NOT NULL"
    )
    op.create_index("ix_assets_hostname", "assets", ["hostname"])
    op.create_index("ix_assets_ip_address", "assets", ["ip_address"])
    op.create_index("ix_assets_source", "assets", ["source"])

    op.add_column("asset_relationships", sa.Column("notes", sa.Text()))


def downgrade() -> None:
    op.drop_column("asset_relationships", "notes")
    op.drop_index("ix_assets_source", table_name="assets")
    op.drop_index("ix_assets_ip_address", table_name="assets")
    op.drop_index("ix_assets_hostname", table_name="assets")
    for column in ("source", "ip_address", "hostname", "model"):
        op.drop_column("assets", column)
    op.drop_index("ix_sites_status", table_name="sites")
    op.drop_column("sites", "status")
    op.drop_index("ix_customers_status", table_name="customers")
    op.drop_column("customers", "status")
