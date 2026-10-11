"""Add scoped generic connections, protected secrets and version-global mappings.

Revision ID: 20261012_0028
Revises: 20261011_0027
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "20261012_0028"
down_revision = "20261011_0027"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_data_sources_identity_scope", "data_sources", ["id", "customer_id", "site_id"])
    op.drop_constraint(op.f("ck_data_sources_valid_source_type"), "data_sources", type_="check")
    op.create_check_constraint("valid_source_type", "data_sources", "source_type IN ('manual','simulated_discovery','proxmox','pbs','docker','unifi','netbox','imported_file','generated_inference','connector')")
    for name, kind in [("connector_id", sa.String(100)), ("connector_version", sa.String(64)),
        ("connector_digest", sa.String(64)), ("data_source_id", pg.UUID()), ("creation_key", pg.UUID()),
        ("credential_reference", pg.UUID()), ("config_schema_version", sa.String(16)),
        ("retired_at", sa.DateTime(timezone=True)), ("last_test_at", sa.DateTime(timezone=True)),
        ("last_test_status", sa.String(50)), ("source_version", sa.String(100)), ("source_compatibility", sa.String(32))]:
        op.add_column("integrations", sa.Column(name, kind))
    for name, default in [("config_json", "{}"), ("selected_scopes", "[]")]:
        op.add_column("integrations", sa.Column(name, pg.JSONB(), nullable=False, server_default=default))
    op.add_column("integrations", sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_integrations_connector_id", "integrations", ["connector_id"])
    op.create_unique_constraint("uq_integrations_identity_scope", "integrations", ["id", "customer_id", "site_id"])
    op.create_unique_constraint("uq_integrations_creation_key", "integrations", ["customer_id", "site_id", "creation_key"])
    op.create_unique_constraint("uq_integrations_data_source", "integrations", ["data_source_id"])
    op.create_foreign_key("fk_integrations_data_source_scope", "integrations", "data_sources", ["data_source_id", "customer_id", "site_id"], ["id", "customer_id", "site_id"], ondelete="RESTRICT")
    op.create_check_constraint("generic_identity", "integrations", "connector_id IS NULL OR (data_source_id IS NOT NULL AND connector_version IS NOT NULL AND connector_digest IS NOT NULL AND config_schema_version IS NOT NULL)")
    op.create_table("integration_secrets",
        sa.Column("id", pg.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("integration_id", pg.UUID(), nullable=False),
        sa.Column("customer_id", pg.UUID(), nullable=False), sa.Column("site_id", pg.UUID(), nullable=False),
        sa.Column("encryption_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("encrypted_fields", pg.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["integration_id", "customer_id", "site_id"], ["integrations.id", "integrations.customer_id", "integrations.site_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("encryption_version = 1", name="encryption_version"))
    op.create_index("ix_integration_secrets_integration_id", "integration_secrets", ["integration_id"])
    op.create_foreign_key("fk_integrations_credential_reference_integration_secrets", "integrations", "integration_secrets", ["credential_reference"], ["id"], ondelete="SET NULL")
    op.create_table("connector_mappings",
        sa.Column("id", pg.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("connector_id", sa.String(100), nullable=False),
        sa.Column("connector_version", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False), sa.Column("source_key", sa.String(100), nullable=False),
        sa.Column("target_key", sa.String(100)), sa.Column("ignored", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("asset_type_key", sa.String(100), sa.ForeignKey("asset_types.key", ondelete="RESTRICT")),
        sa.Column("relationship_type_key", sa.String(100), sa.ForeignKey("relationship_types.key", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("connector_id", "connector_version", "kind", "source_key"),
        sa.CheckConstraint("kind IN ('asset','relationship')", name="mapping_kind"),
        sa.CheckConstraint("(ignored AND target_key IS NULL) OR NOT ignored", name="ignored_target"),
        sa.CheckConstraint("(kind = 'asset' AND target_key IS NOT DISTINCT FROM asset_type_key AND relationship_type_key IS NULL) OR (kind = 'relationship' AND target_key IS NOT DISTINCT FROM relationship_type_key AND asset_type_key IS NULL)", name="mapping_target_fk"))
    op.create_index("ix_connector_mappings_connector_id", "connector_mappings", ["connector_id"])
    op.execute("INSERT INTO permissions (key,name,category,system_defined) VALUES ('integrations.run','Test Integration connections','Integrations',true) ON CONFLICT (key) DO NOTHING")
    op.execute("INSERT INTO role_permissions (role_id,permission_id) SELECT r.id,p.id FROM roles r CROSS JOIN permissions p WHERE r.system_defined AND r.name IN ('Master Administrator','Administrator','Customer Administrator') AND p.key='integrations.run' ON CONFLICT DO NOTHING")


def downgrade():
    # Explicit operator downgrade cannot discard protected connection state.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT count(*) FROM integrations WHERE connector_id IS NOT NULL")):
        raise RuntimeError("Retain generic Integration history before downgrading")
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key='integrations.run')")
    op.execute("DELETE FROM permissions WHERE key='integrations.run'")
    op.drop_table("connector_mappings")
    op.drop_constraint("fk_integrations_credential_reference_integration_secrets", "integrations", type_="foreignkey")
    op.drop_table("integration_secrets")
    op.drop_constraint(op.f("ck_integrations_generic_identity"), "integrations", type_="check")
    op.drop_constraint("fk_integrations_data_source_scope", "integrations", type_="foreignkey")
    for constraint in ["uq_integrations_identity_scope", "uq_integrations_creation_key", "uq_integrations_data_source"]:
        op.drop_constraint(constraint, "integrations", type_="unique")
    op.drop_index("ix_integrations_connector_id", "integrations")
    for name in ["connector_id", "connector_version", "connector_digest", "data_source_id", "creation_key", "credential_reference", "config_schema_version", "config_json", "selected_scopes", "enabled", "retired_at", "last_test_at", "last_test_status", "source_version", "source_compatibility"]:
        op.drop_column("integrations", name)
    op.drop_constraint("uq_data_sources_identity_scope", "data_sources", type_="unique")
    op.drop_constraint(op.f("ck_data_sources_valid_source_type"), "data_sources", type_="check")
    op.create_check_constraint("valid_source_type", "data_sources", "source_type IN ('manual','simulated_discovery','proxmox','pbs','docker','unifi','netbox','imported_file','generated_inference')")
