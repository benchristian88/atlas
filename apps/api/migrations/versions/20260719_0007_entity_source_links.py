"""Add durable source identities for discovered Atlas entities.

Revision ID: 20260719_0007
Revises: 20260719_0006
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0007"
down_revision: str | None = "20260719_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "entity_source_links",
        sa.Column(
            "id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID, nullable=False),
        sa.Column("data_source_id", UUID, nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", UUID, nullable=False),
        sa.Column("external_id", sa.String(1024), nullable=False),
        sa.Column("external_type", sa.String(100)),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("entity_type IN ('asset')", name="valid_entity_type"),
        sa.UniqueConstraint(
            "data_source_id",
            "entity_type",
            "external_id",
            name="uq_entity_source_links_source_type_external",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_entity_source_links_customer_site_sites",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id", "customer_id", "site_id"],
            ["assets.id", "assets.customer_id", "assets.site_id"],
            name="fk_entity_source_links_asset_context",
            ondelete="CASCADE",
        ),
    )
    for column in (
        "customer_id",
        "site_id",
        "data_source_id",
        "entity_type",
        "entity_id",
        "external_id",
        "external_type",
        "last_observed_at",
    ):
        op.create_index(
            f"ix_entity_source_links_{column}", "entity_source_links", [column]
        )


def downgrade() -> None:
    op.drop_table("entity_source_links")
