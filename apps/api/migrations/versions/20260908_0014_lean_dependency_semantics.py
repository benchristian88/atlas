"""Add temporal lean dependency groups and memberships.

Revision ID: 20260908_0014
Revises: 20260720_0013
Create Date: 2026-09-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0014"
down_revision: str | None = "20260720_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
UUID_DEFAULT = sa.text("gen_random_uuid()")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "dependency_groups",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("service_id", UUID, nullable=False),
        sa.Column("supersedes_group_id", UUID),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("strategy", sa.String(20), nullable=False),
        sa.Column("requirement", sa.String(20), nullable=False),
        sa.Column("failure_effect", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", UUID),
        sa.Column("ended_by_user_id", UUID),
        *_timestamps(),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id", "site_id"], ["sites.customer_id", "sites.id"], name="fk_dependency_groups_customer_site_sites", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_group_id"], ["dependency_groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ended_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("strategy IN ('all', 'any')", name=op.f("ck_dependency_groups_valid_strategy")),
        sa.CheckConstraint("requirement IN ('required', 'optional')", name=op.f("ck_dependency_groups_valid_requirement")),
        sa.CheckConstraint("failure_effect IN ('unavailable', 'degraded', 'unknown')", name=op.f("ck_dependency_groups_valid_failure_effect")),
    )
    for column in ("customer_id", "site_id", "service_id", "supersedes_group_id", "valid_to", "created_by_user_id", "ended_by_user_id"):
        op.create_index(f"ix_dependency_groups_{column}", "dependency_groups", [column])
    op.create_index(
        "uq_dependency_groups_active_name",
        "dependency_groups",
        ["service_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )

    op.create_table(
        "dependency_group_memberships",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("dependency_group_id", UUID, nullable=False),
        sa.Column("service_asset_dependency_id", UUID),
        sa.Column("service_dependency_id", UUID),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", UUID),
        sa.Column("ended_by_user_id", UUID),
        *_timestamps(),
        sa.ForeignKeyConstraint(["dependency_group_id"], ["dependency_groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_asset_dependency_id"], ["service_asset_dependencies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_dependency_id"], ["service_dependencies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ended_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "(service_asset_dependency_id IS NOT NULL) <> (service_dependency_id IS NOT NULL)",
            name=op.f("ck_dependency_group_memberships_exactly_one_dependency"),
        ),
    )
    for column in ("dependency_group_id", "service_asset_dependency_id", "service_dependency_id", "valid_to", "created_by_user_id", "ended_by_user_id"):
        op.create_index(f"ix_dependency_group_memberships_{column}", "dependency_group_memberships", [column])
    op.create_index(
        "uq_dependency_group_memberships_active_asset_dependency",
        "dependency_group_memberships",
        ["service_asset_dependency_id"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL AND service_asset_dependency_id IS NOT NULL"),
    )
    op.create_index(
        "uq_dependency_group_memberships_active_service_dependency",
        "dependency_group_memberships",
        ["service_dependency_id"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL AND service_dependency_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("dependency_group_memberships")
    op.drop_table("dependency_groups")
