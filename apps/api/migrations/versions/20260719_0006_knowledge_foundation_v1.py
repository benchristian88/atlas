"""Add provenance, assertions, and reconciliation beside the operational model.

Revision ID: 20260719_0006
Revises: 20260717_0005
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0006"
down_revision: str | None = "20260717_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def uuid_pk() -> sa.Column:
    return sa.Column(
        "id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def upgrade() -> None:
    op.create_table(
        "data_sources",
        uuid_pk(),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("trust_level", sa.String(50)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        *timestamps(),
        sa.CheckConstraint(
            "source_type IN ('manual', 'simulated_discovery', 'proxmox', 'pbs', "
            "'docker', 'unifi', 'netbox', 'imported_file', 'generated_inference')",
            name="valid_source_type",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_data_sources_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )
    for column in ("customer_id", "site_id", "source_type", "status"):
        op.create_index(f"ix_data_sources_{column}", "data_sources", [column])

    op.add_column("discovery_runs", sa.Column("data_source_id", UUID))
    op.add_column("discovery_runs", sa.Column("customer_id", UUID))
    op.add_column("discovery_runs", sa.Column("site_id", UUID))
    op.add_column("discovery_runs", sa.Column("finished_at", sa.DateTime(timezone=True)))
    op.add_column("discovery_runs", sa.Column("created_by_user_id", UUID))
    op.add_column(
        "discovery_runs",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column(
        "discovery_runs",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute(
        """
        UPDATE discovery_runs AS run
        SET customer_id = integration.customer_id,
            site_id = integration.site_id,
            started_at = COALESCE(run.started_at, now()),
            finished_at = run.completed_at,
            created_at = COALESCE(run.started_at, now()),
            updated_at = COALESCE(run.completed_at, run.started_at, now())
        FROM integrations AS integration
        WHERE integration.id = run.integration_id
        """
    )
    op.alter_column("discovery_runs", "integration_id", existing_type=UUID, nullable=True)
    op.alter_column(
        "discovery_runs",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.alter_column("discovery_runs", "customer_id", existing_type=UUID, nullable=False)
    op.create_foreign_key(
        "fk_discovery_runs_data_source_id_data_sources",
        "discovery_runs",
        "data_sources",
        ["data_source_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_discovery_runs_customer_id_customers",
        "discovery_runs",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_discovery_runs_customer_site_sites",
        "discovery_runs",
        "sites",
        ["customer_id", "site_id"],
        ["customer_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_discovery_runs_created_by_user_id_users",
        "discovery_runs",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "valid_status",
        "discovery_runs",
        "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
    )
    for column in ("data_source_id", "customer_id", "site_id", "created_by_user_id"):
        op.create_index(f"ix_discovery_runs_{column}", "discovery_runs", [column])

    op.create_table(
        "evidence_records",
        uuid_pk(),
        sa.Column("discovery_run_id", UUID, nullable=False),
        sa.Column("data_source_id", UUID, nullable=False),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("external_id", sa.String(1024)),
        sa.Column("entity_kind", sa.String(100), nullable=False),
        sa.Column("payload_json", JSONB, nullable=False),
        sa.Column("payload_hash", sa.String(64)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["discovery_run_id"], ["discovery_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_evidence_records_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )
    for column in (
        "discovery_run_id", "data_source_id", "customer_id", "site_id",
        "external_id", "entity_kind", "payload_hash", "observed_at",
    ):
        op.create_index(f"ix_evidence_records_{column}", "evidence_records", [column])

    op.create_table(
        "knowledge_assertions",
        uuid_pk(),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("subject_type", sa.String(100), nullable=False),
        sa.Column("subject_id", UUID),
        sa.Column("subject_external_id", sa.String(1024)),
        sa.Column("predicate", sa.String(255), nullable=False),
        sa.Column("value_json", JSONB),
        sa.Column("object_type", sa.String(100)),
        sa.Column("object_id", UUID),
        sa.Column("object_external_id", sa.String(1024)),
        sa.Column("truth_classification", sa.String(30), nullable=False),
        sa.Column("confirmation_status", sa.String(30), nullable=False, server_default="unreviewed"),
        sa.Column("data_source_id", UUID),
        sa.Column("discovery_run_id", UUID),
        sa.Column("evidence_record_id", UUID),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="1.0"),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("superseded_by_id", UUID),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *timestamps(),
        sa.CheckConstraint(
            "truth_classification IN ('observed', 'declared', 'intended', 'inferred')",
            name="valid_truth_classification",
        ),
        sa.CheckConstraint(
            "confirmation_status IN ('unreviewed', 'confirmed', 'rejected', 'superseded', 'conflicted')",
            name="valid_confirmation_status",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="valid_confidence",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_knowledge_assertions_customer_site_sites",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["discovery_run_id"], ["discovery_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["evidence_record_id"], ["evidence_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["knowledge_assertions.id"], ondelete="SET NULL"),
    )
    for column in (
        "customer_id", "site_id", "subject_type", "subject_id",
        "subject_external_id", "predicate", "object_type", "object_id",
        "object_external_id", "truth_classification", "confirmation_status",
        "data_source_id", "discovery_run_id", "evidence_record_id",
        "last_observed_at", "superseded_by_id", "is_current",
    ):
        op.create_index(f"ix_knowledge_assertions_{column}", "knowledge_assertions", [column])

    op.create_table(
        "reconciliation_items",
        uuid_pk(),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", UUID),
        sa.Column("candidate_external_id", sa.String(1024)),
        sa.Column("assertion_id", UUID, nullable=False),
        sa.Column("current_value_json", JSONB),
        sa.Column("observed_value_json", JSONB),
        sa.Column("recommended_action", sa.String(255)),
        sa.Column("decision_reason", sa.Text()),
        sa.Column("decided_by_user_id", UUID),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint(
            "category IN ('newly_discovered', 'changed', 'no_longer_observed', "
            "'contradiction', 'possible_duplicate', 'missing_classification', "
            "'inferred_relationship', 'stale_human_knowledge')",
            name="valid_category",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'accepted', 'rejected', 'deferred', 'exception')",
            name="valid_status",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_reconciliation_items_customer_site_sites",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["assertion_id"], ["knowledge_assertions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in (
        "customer_id", "site_id", "category", "status", "entity_type",
        "entity_id", "candidate_external_id", "assertion_id", "decided_by_user_id",
    ):
        op.create_index(f"ix_reconciliation_items_{column}", "reconciliation_items", [column])


def downgrade() -> None:
    op.drop_table("reconciliation_items")
    op.drop_table("knowledge_assertions")
    op.drop_table("evidence_records")
    op.execute("DELETE FROM discovery_runs WHERE integration_id IS NULL")
    op.drop_constraint(
        op.f("ck_discovery_runs_valid_status"), "discovery_runs", type_="check"
    )
    for column in ("created_by_user_id", "site_id", "customer_id", "data_source_id"):
        op.drop_index(f"ix_discovery_runs_{column}", table_name="discovery_runs")
    op.drop_constraint(
        "fk_discovery_runs_created_by_user_id_users", "discovery_runs", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_discovery_runs_customer_site_sites", "discovery_runs", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_discovery_runs_customer_id_customers", "discovery_runs", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_discovery_runs_data_source_id_data_sources", "discovery_runs", type_="foreignkey"
    )
    op.alter_column("discovery_runs", "integration_id", existing_type=UUID, nullable=False)
    op.alter_column(
        "discovery_runs",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    for column in (
        "updated_at", "created_at", "created_by_user_id", "finished_at",
        "site_id", "customer_id", "data_source_id",
    ):
        op.drop_column("discovery_runs", column)
    op.drop_table("data_sources")
