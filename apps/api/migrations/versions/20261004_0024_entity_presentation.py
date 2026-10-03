"""Add optional Service Type and Business Function presentation identity.

Revision ID: 20261004_0024
Revises: 20260921_0023
"""
from alembic import op
import sqlalchemy as sa

revision = "20261004_0024"
down_revision = "20260921_0023"
branch_labels = None
depends_on = None


def upgrade():
    # Null retains historical records unchanged; renderers resolve stable defaults.
    op.add_column("service_types", sa.Column("accent_key", sa.String(32), nullable=True))
    op.add_column("business_functions", sa.Column("icon_key", sa.String(32), nullable=True))
    op.add_column("business_functions", sa.Column("accent_key", sa.String(32), nullable=True))


def downgrade():
    op.drop_column("business_functions", "accent_key")
    op.drop_column("business_functions", "icon_key")
    op.drop_column("service_types", "accent_key")
