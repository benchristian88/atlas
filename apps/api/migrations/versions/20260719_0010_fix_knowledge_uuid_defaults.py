"""Restore UUID defaults for knowledge foundation v2 tables.

Revision ID: 20260719_0010
Revises: 20260719_0009
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0010"
down_revision: str | None = "20260719_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
UUID_SERVER_DEFAULT = sa.text("gen_random_uuid()")


def upgrade() -> None:
    for table_name in ("run_observed_entities", "knowledge_changes"):
        op.alter_column(
            table_name,
            "id",
            existing_type=UUID,
            existing_nullable=False,
            server_default=UUID_SERVER_DEFAULT,
        )


def downgrade() -> None:
    for table_name in ("knowledge_changes", "run_observed_entities"):
        op.alter_column(
            table_name,
            "id",
            existing_type=UUID,
            existing_nullable=False,
            server_default=None,
        )
