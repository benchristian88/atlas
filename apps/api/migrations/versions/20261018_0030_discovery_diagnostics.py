"""Add bounded discovery diagnostics and one-shot debug intent.

Revision ID: 20261018_0030
Revises: 20261012_0029
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "20261018_0030"
down_revision = "20261012_0029"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("integrations", sa.Column("debug_next_run", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("discovery_runs", sa.Column("debug_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    for name in ["debug_expires_at", "debug_deleted_at"]:
        op.add_column("discovery_runs", sa.Column(name, sa.DateTime(timezone=True)))
    for name in ["diagnostics_summary", "diagnostics_events"]:
        op.add_column("discovery_runs", sa.Column(name, pg.JSONB()))
    op.create_check_constraint("debug_intent", "discovery_runs", "(debug_enabled AND execution_provenance IS NOT NULL AND debug_expires_at IS NOT NULL AND debug_expires_at <= created_at + interval '48 hours') OR (NOT debug_enabled AND debug_expires_at IS NULL)")
    op.create_table("discovery_run_debug_traces",
        sa.Column("discovery_run_id", pg.UUID(as_uuid=True), sa.ForeignKey("discovery_runs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("events", pg.JSONB(), nullable=False),
        sa.CheckConstraint("jsonb_typeof(events) = 'array' AND jsonb_array_length(events) <= 8192 AND octet_length(events::text) <= 7340032", name="bounded_events"))
    op.create_index("ix_discovery_run_debug_traces_expires_at", "discovery_run_debug_traces", ["expires_at"])
    op.execute("""
        CREATE FUNCTION atlas_discovery_debug_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'UPDATE' AND (NEW.debug_enabled IS DISTINCT FROM OLD.debug_enabled OR
              NEW.debug_expires_at IS DISTINCT FROM OLD.debug_expires_at) THEN
            RAISE EXCEPTION 'Discovery debug intent is immutable';
          END IF;
          IF NEW.execution_provenance IS NOT NULL AND
              NEW.debug_enabled IS DISTINCT FROM COALESCE((NEW.execution_provenance->>'debug_enabled')::boolean, false) THEN
            RAISE EXCEPTION 'Discovery debug provenance is invalid';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER discovery_debug_immutable BEFORE INSERT OR UPDATE ON discovery_runs
        FOR EACH ROW EXECUTE FUNCTION atlas_discovery_debug_immutable();
    """)


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM discovery_runs WHERE debug_enabled OR diagnostics_summary IS NOT NULL")):
        raise RuntimeError("Retain discovery diagnostics history before downgrading")
    op.execute("DROP TRIGGER discovery_debug_immutable ON discovery_runs")
    op.execute("DROP FUNCTION atlas_discovery_debug_immutable()")
    op.drop_table("discovery_run_debug_traces")
    op.drop_constraint(op.f("ck_discovery_runs_debug_intent"), "discovery_runs", type_="check")
    for name in ["debug_enabled", "debug_expires_at", "debug_deleted_at", "diagnostics_summary", "diagnostics_events"]:
        op.drop_column("discovery_runs", name)
    op.drop_column("integrations", "debug_next_run")
