"""Add the per-user accent colour preference.

Revision ID: 20260717_0005
Revises: 20260714_0004
Create Date: 2026-07-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260717_0005"
down_revision: str | None = "20260714_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("accent_colour", sa.String(7), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "accent_colour")
