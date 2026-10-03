"""Add an independent per-user theme mode preference.

Revision ID: 20260909_0015
Revises: 20260908_0014
Create Date: 2026-09-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260909_0015"
down_revision: str | None = "20260908_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing accounts retain OS-based appearance; no data backfill is needed.
    op.add_column("users", sa.Column("theme_mode", sa.String(6), nullable=True))
    op.create_check_constraint(
        op.f("ck_users_theme_mode"), "users", "theme_mode IN ('light', 'dark', 'system')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_theme_mode"), "users", type_="check")
    op.drop_column("users", "theme_mode")
