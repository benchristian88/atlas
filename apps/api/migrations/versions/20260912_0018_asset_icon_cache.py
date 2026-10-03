"""Add disposable, bounded Asset icon cache in existing persistent PostgreSQL.

Revision ID: 20260912_0018
Revises: 20260910_0017
"""
from alembic import op
import sqlalchemy as sa

revision = "20260912_0018"
down_revision = "20260910_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_icon_cache",
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_hash", sa.String(64)),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("data", sa.LargeBinary()),
        sa.Column("attempted_source_hash", sa.String(64), nullable=False),
        sa.Column("retry_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_token", sa.Uuid(), nullable=False),
        sa.CheckConstraint("octet_length(data) <= 524288", name="bounded_icon_data"),
    )


def downgrade() -> None:
    op.drop_table("asset_icon_cache")
