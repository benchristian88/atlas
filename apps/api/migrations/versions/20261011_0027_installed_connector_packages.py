"""Instance-global verified active Connector identities; no scoped config changes.

Revision ID: 20261011_0027
Revises: 20261004_0026
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261011_0027"
down_revision = "20261004_0026"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("installed_connector_packages",
        sa.Column("connector_id", sa.String(100), primary_key=True),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("bundle_digest", sa.String(64), nullable=False),
        sa.Column("manifest_version", sa.String(16), nullable=False),
        sa.Column("protocol_version", sa.String(64), nullable=False),
        sa.Column("publisher_id", sa.String(100), nullable=False),
        sa.Column("trust_tier", sa.String(32), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False),
        sa.Column("verification_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("runtime_baseline_id", sa.String(100), nullable=False),
        sa.Column("runtime_baseline_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("verification_status = 'verified'", name="verified_only"),
        sa.CheckConstraint("status = 'active'", name="active_only"),
        sa.CheckConstraint("length(bundle_digest) = 64", name="digest_length"),
    )
    for key, name in (
        ("integration_runtime.view", "Inspect the local integration runtime"),
        ("integration_runtime.manage", "Manage global Connector packages"),
    ):
        op.execute(sa.text("""
            INSERT INTO permissions (key, name, category, system_defined)
            VALUES (:key, :name, 'Integrations', true)
            ON CONFLICT (key) DO NOTHING
        """).bindparams(key=key, name=name))
    # Scoped assignments never gain global execution authority. The API also
    # checks the global grant on every runtime/admin route.
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name IN ('Master Administrator', 'Administrator')
          AND r.system_defined
          AND p.key IN ('integration_runtime.view', 'integration_runtime.manage')
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key IN ('integration_runtime.view', 'integration_runtime.manage'))")
    op.execute("DELETE FROM permissions WHERE key IN ('integration_runtime.view', 'integration_runtime.manage')")
    op.drop_table("installed_connector_packages")
