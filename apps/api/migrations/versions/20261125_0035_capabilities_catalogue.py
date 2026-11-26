"""Persist the shared Capabilities draft and atomic Apply outcomes.

Revision ID: 20261125_0035
Revises: 20261122_0034
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261125_0035"
down_revision = "20261122_0034"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("site_onboarding", sa.Column("capabilities_draft", postgresql.JSONB()))
    op.create_table(
        "onboarding_capability_submissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("onboarding_id", sa.Uuid(), sa.ForeignKey("site_onboarding.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_version", sa.Integer(), nullable=False),
        sa.Column("outcome", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "ix_onboarding_capability_submissions_onboarding_id",
        "onboarding_capability_submissions",
        ["onboarding_id"],
    )


def downgrade():
    op.drop_table("onboarding_capability_submissions")
    op.drop_column("site_onboarding", "capabilities_draft")
