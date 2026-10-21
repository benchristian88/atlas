"""Instance-global official catalogue history and refresh checkpoint.

Revision ID: 20261021_0031
Revises: 20261018_0030
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "20261021_0031"
down_revision = "20261018_0030"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("connector_catalogue_revisions",
        sa.Column("sequence", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("original_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification_evidence", pg.JSONB(), nullable=False),
        sa.Column("publication_evidence", pg.JSONB(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("sequence", "content_digest", name="uq_catalogue_revision_identity"),
        sa.CheckConstraint("sequence BETWEEN 1 AND 9007199254740991", name="sequence_range"),
        sa.CheckConstraint("length(content_digest) = 64", name="digest_length"),
        sa.CheckConstraint("octet_length(original_bytes) BETWEEN 1 AND 4194304", name="bounded_bytes"),
        sa.CheckConstraint("octet_length(verification_evidence::text) <= 65536", name="bounded_evidence"))
    op.create_table("connector_catalogue_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("highest_sequence", sa.BigInteger()),
        sa.Column("highest_digest", sa.String(64)),
        sa.Column("identity_history", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *[sa.Column(name, sa.DateTime(timezone=True)) for name in (
            "last_attempt_at", "last_download_at", "last_authenticity_verified_at",
            "last_confirmed_current_at", "lease_until", "next_attempt_at")],
        sa.Column("operation_id", pg.UUID(as_uuid=True)),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("source_conflict", sa.String(100)),
        sa.CheckConstraint("id = 1", name="singleton"),
        sa.CheckConstraint("(highest_sequence IS NULL) = (highest_digest IS NULL)", name="checkpoint_pair"),
        sa.CheckConstraint("(operation_id IS NULL) = (lease_until IS NULL)", name="lease_pair"),
        sa.CheckConstraint("octet_length(identity_history::text) <= 2097152", name="bounded_history"),
        sa.ForeignKeyConstraint(["highest_sequence", "highest_digest"],
            ["connector_catalogue_revisions.sequence", "connector_catalogue_revisions.content_digest"],
            name="fk_catalogue_checkpoint"))
    op.execute("INSERT INTO connector_catalogue_state (id) VALUES (1)")
    op.execute("""
        CREATE FUNCTION atlas_catalogue_revision_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Accepted catalogue history is immutable'; END $$;
        CREATE TRIGGER catalogue_revision_immutable BEFORE UPDATE OR DELETE ON connector_catalogue_revisions
        FOR EACH ROW EXECUTE FUNCTION atlas_catalogue_revision_immutable();
        CREATE FUNCTION atlas_catalogue_checkpoint_monotonic() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Catalogue checkpoint cannot be deleted'; END IF;
          IF OLD.highest_sequence IS NOT NULL AND (NEW.highest_sequence IS NULL OR
              NEW.highest_sequence < OLD.highest_sequence OR
              (NEW.highest_sequence = OLD.highest_sequence AND NEW.highest_digest IS DISTINCT FROM OLD.highest_digest)) THEN
            RAISE EXCEPTION 'Catalogue checkpoint cannot decrease or change identity';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER catalogue_checkpoint_monotonic BEFORE UPDATE OR DELETE ON connector_catalogue_state
        FOR EACH ROW EXECUTE FUNCTION atlas_catalogue_checkpoint_monotonic();
    """)


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM connector_catalogue_revisions")):
        raise RuntimeError("Retain authenticated catalogue history before downgrading")
    op.drop_table("connector_catalogue_state")
    op.drop_table("connector_catalogue_revisions")
    op.execute("DROP FUNCTION atlas_catalogue_checkpoint_monotonic()")
    op.execute("DROP FUNCTION atlas_catalogue_revision_immutable()")
