"""Bounded category and Network presentation metadata.

Revision ID: 20260921_0020
Revises: 20260921_0019
"""
from alembic import op
import sqlalchemy as sa

revision = "20260921_0020"
down_revision = "20260921_0019"
branch_labels = None
depends_on = None


def upgrade():
    for table, icon, accent in (("asset_categories", "infrastructure", "slate"), ("networks", "network", "blue")):
        op.add_column(table, sa.Column("icon_key", sa.String(32), nullable=False, server_default=icon))
        op.add_column(table, sa.Column("accent_key", sa.String(32), nullable=False, server_default=accent))
    # Exact known labels only, once at upgrade. Unknown/custom taxonomy is retained.
    defaults = {
        "Compute": ("server", "blue"), "Software": ("cube", "green"),
        "Workload": ("cube", "green"), "Network": ("network", "cyan"),
        "Storage": ("database", "purple"), "Backup": ("archive", "orange"),
        "Data": ("database", "teal"),
    }
    for name, (icon, accent) in defaults.items():
        op.get_bind().execute(sa.text(
            "UPDATE asset_categories SET icon_key=:icon, accent_key=:accent WHERE name=:name"
        ), {"name": name, "icon": icon, "accent": accent})


def downgrade():
    for table in ("networks", "asset_categories"):
        op.drop_column(table, "accent_key")
        op.drop_column(table, "icon_key")
