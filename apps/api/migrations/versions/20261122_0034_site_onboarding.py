"""Add shared Site onboarding and personal invitation dismissal.

Revision ID: 20261122_0034
Revises: 20261119_0033
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261122_0034"
down_revision = "20261119_0033"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("installation_state", sa.Column("onboarding_customer_id", sa.Uuid()))
    op.add_column("installation_state", sa.Column("onboarding_site_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_installation_state_onboarding_customer_id_sites", "installation_state", "sites",
        ["onboarding_customer_id", "onboarding_site_id"], ["customer_id", "id"],
        match="FULL", ondelete="SET NULL", onupdate="SET NULL",
    )
    op.create_table(
        "site_onboarding",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("site_id", sa.Uuid(), unique=True),
        sa.Column("customer_id", sa.Uuid()),
        sa.Column("environment_profile", sa.String(50)),
        sa.Column("draft_profile", sa.String(50)),
        sa.Column("draft_only", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("current_stage", sa.String(50), nullable=False, server_default="environment"),
        sa.Column("stage_decisions", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.ForeignKeyConstraint(
            ["customer_id", "site_id"], ["sites.customer_id", "sites.id"],
            match="FULL", ondelete="SET NULL", onupdate="SET NULL",
        ),
        sa.CheckConstraint("site_id IS NOT NULL OR draft_only", name="detached_draft_only"),
        sa.CheckConstraint(
            "NOT draft_only OR (draft_profile IS NOT NULL AND environment_profile IS NULL "
            "AND current_stage = 'environment' AND status <> 'completed')",
            name="unconfirmed_draft",
        ),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("status IN ('in_progress', 'saved', 'completed')", name="valid_status"),
        sa.CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="completed_timestamp"),
    )
    op.create_table(
        "onboarding_invitation_dismissals",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("onboarding_invitation_dismissals")
    op.drop_table("site_onboarding")
    op.drop_constraint("fk_installation_state_onboarding_customer_id_sites", "installation_state", type_="foreignkey")
    op.drop_column("installation_state", "onboarding_site_id")
    op.drop_column("installation_state", "onboarding_customer_id")
