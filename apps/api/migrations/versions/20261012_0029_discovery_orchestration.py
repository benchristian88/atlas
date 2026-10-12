"""Durable generic discovery intent, immutable execution provenance and receipts.

Revision ID: 20261012_0029
Revises: 20261012_0028
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "20261012_0029"
down_revision = "20261012_0028"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_networks_identity_scope", "networks", ["id", "customer_id", "site_id"])
    op.create_unique_constraint("uq_asset_interfaces_identity_owner", "asset_interfaces", ["id", "asset_id"])
    op.add_column("entity_source_links", sa.Column("network_id", pg.UUID()))
    op.add_column("entity_source_links", sa.Column("interface_id", pg.UUID()))
    op.add_column("entity_source_links", sa.Column("interface_owner_id", pg.UUID()))
    op.alter_column("entity_source_links", "entity_id", nullable=True)
    op.drop_constraint(op.f("ck_entity_source_links_valid_entity_type"), "entity_source_links", type_="check")
    op.create_check_constraint("valid_entity_type", "entity_source_links", "entity_type IN ('asset','network','asset_interface')")
    op.create_check_constraint("target_identity", "entity_source_links", "(entity_type = 'asset' AND entity_id IS NOT NULL AND network_id IS NULL AND interface_id IS NULL AND interface_owner_id IS NULL) OR (entity_type = 'network' AND entity_id IS NULL AND network_id IS NOT NULL AND interface_id IS NULL AND interface_owner_id IS NULL) OR (entity_type = 'asset_interface' AND entity_id IS NULL AND network_id IS NULL AND interface_id IS NOT NULL AND interface_owner_id IS NOT NULL)")
    op.create_foreign_key("fk_entity_source_links_network_context", "entity_source_links", "networks",
        ["network_id", "customer_id", "site_id"], ["id", "customer_id", "site_id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_entity_source_links_interface_owner", "entity_source_links", "asset_interfaces",
        ["interface_id", "interface_owner_id"], ["id", "asset_id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_entity_source_links_interface_context", "entity_source_links", "assets",
        ["interface_owner_id", "customer_id", "site_id"], ["id", "customer_id", "site_id"], ondelete="RESTRICT")
    op.add_column("knowledge_assertions", sa.Column("fact_metadata", pg.JSONB()))
    op.create_foreign_key("fk_discovery_runs_integration_scope", "discovery_runs", "integrations",
        ["integration_id", "customer_id", "site_id"], ["id", "customer_id", "site_id"], ondelete="RESTRICT")
    op.add_column("integrations", sa.Column("schedule_preset", sa.String(16), nullable=False, server_default="manual"))
    for name in ["next_run_at", "last_run_at", "last_success_at"]:
        op.add_column("integrations", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column("integrations", sa.Column("last_error_code", sa.String(64)))
    op.create_check_constraint("schedule_preset", "integrations", "schedule_preset IN ('manual','hourly','6_hours','12_hours','daily','weekly')")
    op.create_index("ix_integrations_next_run_at", "integrations", ["next_run_at"])
    for name, kind in [("execution_provenance", pg.JSONB()), ("dispatch_after", sa.DateTime(timezone=True)),
            ("runtime_job_id", pg.UUID()), ("ingestion_generation", pg.UUID()), ("deadline_at", sa.DateTime(timezone=True)),
            ("cancellation_requested_at", sa.DateTime(timezone=True)), ("finalisation_hash", sa.String(64)),
            ("source_version", sa.String(100))]:
        op.add_column("discovery_runs", sa.Column(name, kind))
    op.add_column("discovery_runs", sa.Column("dispatch_state", sa.String(16), nullable=False, server_default="pending"))
    for name in ["dispatch_attempts", "batch_count", "observation_count", "warning_count"]:
        op.add_column("discovery_runs", sa.Column(name, sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_discovery_runs_dispatch_after", "discovery_runs", ["dispatch_after"])
    op.create_check_constraint("dispatch_attempts", "discovery_runs", "dispatch_attempts >= 0 AND dispatch_attempts <= 3")
    op.create_check_constraint("dispatch_state", "discovery_runs", "dispatch_state IN ('pending','dispatching','running','settled')")
    # Legacy history has no execution provenance and is preserved unchanged.
    op.create_index("uq_discovery_runs_active_integration", "discovery_runs", ["integration_id"], unique=True,
        postgresql_where=sa.text("execution_provenance IS NOT NULL AND (status IN ('pending','running') OR dispatch_state != 'settled')"))
    op.create_table("discovery_batch_receipts",
        sa.Column("discovery_run_id", pg.UUID(), sa.ForeignKey("discovery_runs.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("sequence", sa.Integer(), primary_key=True),
        sa.Column("body_hash", sa.String(64), nullable=False),
        sa.Column("payload_json", pg.JSONB(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("sequence BETWEEN 1 AND 10000", name="sequence"))
    op.execute("""
        CREATE FUNCTION atlas_discovery_provenance_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.execution_provenance IS NOT NULL AND NOT EXISTS (
             SELECT 1 FROM integrations WHERE id = NEW.integration_id
              AND data_source_id = NEW.data_source_id AND customer_id = NEW.customer_id AND site_id = NEW.site_id) THEN
            RAISE EXCEPTION 'Discovery integration source context is invalid';
          END IF;
          IF TG_OP = 'UPDATE' AND OLD.execution_provenance IS NOT NULL AND
             (NEW.execution_provenance IS DISTINCT FROM OLD.execution_provenance OR
              NEW.integration_id IS DISTINCT FROM OLD.integration_id OR
              NEW.data_source_id IS DISTINCT FROM OLD.data_source_id OR
              NEW.customer_id IS DISTINCT FROM OLD.customer_id OR
              NEW.site_id IS DISTINCT FROM OLD.site_id OR
              NEW.coverage_key IS DISTINCT FROM OLD.coverage_key OR
              NEW.is_complete_snapshot IS DISTINCT FROM OLD.is_complete_snapshot) THEN
            RAISE EXCEPTION 'Discovery execution provenance is immutable';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER discovery_provenance_immutable BEFORE INSERT OR UPDATE ON discovery_runs
        FOR EACH ROW EXECUTE FUNCTION atlas_discovery_provenance_immutable();
        CREATE FUNCTION atlas_discovery_receipt_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'Discovery receipts are immutable';
        END $$;
        CREATE TRIGGER discovery_receipt_immutable BEFORE UPDATE OR DELETE ON discovery_batch_receipts
        FOR EACH ROW EXECUTE FUNCTION atlas_discovery_receipt_immutable();
    """)


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT count(*) FROM discovery_runs WHERE execution_provenance IS NOT NULL")):
        raise RuntimeError("Retain discovery execution history before downgrading")
    if connection.scalar(sa.text("SELECT count(*) FROM entity_source_links WHERE entity_type != 'asset'")):
        raise RuntimeError("Retain technical source identity before downgrading")
    for name in ["fk_entity_source_links_network_context", "fk_entity_source_links_interface_owner", "fk_entity_source_links_interface_context"]:
        op.drop_constraint(name, "entity_source_links", type_="foreignkey")
    op.drop_constraint(op.f("ck_entity_source_links_target_identity"), "entity_source_links", type_="check")
    op.drop_constraint(op.f("ck_entity_source_links_valid_entity_type"), "entity_source_links", type_="check")
    op.create_check_constraint("valid_entity_type", "entity_source_links", "entity_type IN ('asset')")
    op.alter_column("entity_source_links", "entity_id", nullable=False)
    for name in ["network_id", "interface_id", "interface_owner_id"]:
        op.drop_column("entity_source_links", name)
    op.drop_constraint("uq_networks_identity_scope", "networks", type_="unique")
    op.drop_constraint("uq_asset_interfaces_identity_owner", "asset_interfaces", type_="unique")
    op.drop_constraint("fk_discovery_runs_integration_scope", "discovery_runs", type_="foreignkey")
    op.drop_column("knowledge_assertions", "fact_metadata")
    op.execute("DROP TRIGGER discovery_receipt_immutable ON discovery_batch_receipts")
    op.execute("DROP FUNCTION atlas_discovery_receipt_immutable()")
    op.drop_table("discovery_batch_receipts")
    op.execute("DROP TRIGGER discovery_provenance_immutable ON discovery_runs")
    op.execute("DROP FUNCTION atlas_discovery_provenance_immutable()")
    op.drop_index("uq_discovery_runs_active_integration", "discovery_runs")
    op.drop_index("ix_discovery_runs_dispatch_after", "discovery_runs")
    op.drop_constraint(op.f("ck_discovery_runs_dispatch_attempts"), "discovery_runs", type_="check")
    op.drop_constraint(op.f("ck_discovery_runs_dispatch_state"), "discovery_runs", type_="check")
    for name in ["execution_provenance", "dispatch_after", "runtime_job_id", "ingestion_generation", "deadline_at",
            "cancellation_requested_at", "finalisation_hash", "source_version", "dispatch_state", "dispatch_attempts",
            "batch_count", "observation_count", "warning_count"]:
        op.drop_column("discovery_runs", name)
    op.drop_index("ix_integrations_next_run_at", "integrations")
    op.drop_constraint(op.f("ck_integrations_schedule_preset"), "integrations", type_="check")
    for name in ["schedule_preset", "next_run_at", "last_run_at", "last_success_at", "last_error_code"]:
        op.drop_column("integrations", name)
