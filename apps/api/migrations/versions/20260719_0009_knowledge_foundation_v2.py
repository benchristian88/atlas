"""Add discovery coverage observations and meaningful knowledge changes.

Revision ID: 20260719_0009
Revises: 20260719_0008
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0009"
down_revision: str | None = "20260719_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())

PERMISSIONS = {
    "changes.view": ("View meaningful knowledge changes", "Knowledge"),
    "reconciliation.view": ("View reconciliation queues", "Reconciliation"),
    "reconciliation.decide": ("Decide reconciliation items", "Reconciliation"),
    "discovery.simulate": ("Run simulated discovery", "Discovery"),
}


def upgrade() -> None:
    op.add_column("discovery_runs", sa.Column("coverage_key", sa.String(1024)))
    op.add_column(
        "discovery_runs",
        sa.Column(
            "is_complete_snapshot",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "discovery_runs",
        sa.Column(
            "completeness_status",
            sa.String(30),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.create_check_constraint(
        "valid_completeness_status",
        "discovery_runs",
        "completeness_status IN ('complete', 'partial', 'failed', 'unknown')",
    )
    op.create_index("ix_discovery_runs_coverage_key", "discovery_runs", ["coverage_key"])
    op.create_index(
        "ix_discovery_runs_is_complete_snapshot",
        "discovery_runs",
        ["is_complete_snapshot"],
    )
    op.create_index(
        "ix_discovery_runs_completeness_status",
        "discovery_runs",
        ["completeness_status"],
    )

    op.create_table(
        "run_observed_entities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("discovery_run_id", UUID, nullable=False),
        sa.Column("data_source_id", UUID, nullable=False),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("coverage_key", sa.String(1024), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(1024), nullable=False),
        sa.Column("entity_id", UUID),
        sa.Column("evidence_record_id", UUID),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["discovery_run_id"], ["discovery_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_record_id"], ["evidence_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_run_observed_entities_customer_site_sites",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "discovery_run_id",
            "entity_type",
            "external_id",
            name="uq_run_observed_entities_run_type_external",
        ),
    )
    for column in (
        "discovery_run_id",
        "data_source_id",
        "customer_id",
        "site_id",
        "coverage_key",
        "entity_type",
        "external_id",
        "entity_id",
        "evidence_record_id",
        "observed_at",
    ):
        op.create_index(
            f"ix_run_observed_entities_{column}",
            "run_observed_entities",
            [column],
        )

    op.create_table(
        "knowledge_changes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("change_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", UUID),
        sa.Column("entity_name_snapshot", sa.String(1024), nullable=False),
        sa.Column("predicate", sa.String(255)),
        sa.Column("previous_value_json", JSONB),
        sa.Column("new_value_json", JSONB),
        sa.Column("truth_classification", sa.String(30)),
        sa.Column("data_source_id", UUID),
        sa.Column("discovery_run_id", UUID),
        sa.Column("assertion_id", UUID),
        sa.Column("reconciliation_item_id", UUID),
        sa.Column("actor_user_id", UUID),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_knowledge_changes_customer_site_sites",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["discovery_run_id"], ["discovery_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assertion_id"], ["knowledge_assertions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reconciliation_item_id"], ["reconciliation_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in (
        "customer_id",
        "site_id",
        "change_type",
        "entity_type",
        "entity_id",
        "predicate",
        "truth_classification",
        "data_source_id",
        "discovery_run_id",
        "assertion_id",
        "reconciliation_item_id",
        "actor_user_id",
        "occurred_at",
    ):
        op.create_index(f"ix_knowledge_changes_{column}", "knowledge_changes", [column])
    op.create_index(
        "ix_knowledge_changes_customer_site_occurred",
        "knowledge_changes",
        ["customer_id", "site_id", "occurred_at"],
    )
    op.create_index(
        "ix_knowledge_changes_entity_occurred",
        "knowledge_changes",
        ["entity_type", "entity_id", "occurred_at"],
    )
    op.create_index(
        "ix_knowledge_changes_type_occurred",
        "knowledge_changes",
        ["change_type", "occurred_at"],
    )
    op.create_index(
        "ix_knowledge_changes_source_run",
        "knowledge_changes",
        ["data_source_id", "discovery_run_id"],
    )

    permission_table = sa.table(
        "permissions",
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("category", sa.String()),
        sa.column("system_defined", sa.Boolean()),
    )
    for key, (name, category) in PERMISSIONS.items():
        op.execute(
            postgresql.insert(permission_table)
            .values(
                key=key,
                name=name,
                description=f"Built-in {name.lower()} permission.",
                category=category,
                system_defined=True,
            )
            .on_conflict_do_nothing(index_elements=["key"])
        )
        role_names = ["Master Administrator", "Administrator", "Customer Administrator"]
        if key in {"changes.view", "reconciliation.view"}:
            role_names.append("Viewer")
        for role_name in role_names:
            op.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT roles.id, permissions.id
                    FROM roles, permissions
                    WHERE roles.name = :role_name AND permissions.key = :permission_key
                    ON CONFLICT (role_id, permission_id) DO NOTHING
                    """
                ).bindparams(role_name=role_name, permission_key=key)
            )


def downgrade() -> None:
    keys = tuple(PERMISSIONS)
    op.execute(
        sa.text(
            "DELETE FROM role_permissions USING permissions "
            "WHERE role_permissions.permission_id = permissions.id "
            "AND permissions.key IN :keys"
        ).bindparams(sa.bindparam("keys", expanding=True, value=keys))
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE key IN :keys").bindparams(
            sa.bindparam("keys", expanding=True, value=keys)
        )
    )

    op.drop_table("knowledge_changes")
    op.drop_table("run_observed_entities")
    op.drop_index("ix_discovery_runs_completeness_status", table_name="discovery_runs")
    op.drop_index("ix_discovery_runs_is_complete_snapshot", table_name="discovery_runs")
    op.drop_index("ix_discovery_runs_coverage_key", table_name="discovery_runs")
    op.drop_constraint(
        "valid_completeness_status",
        "discovery_runs",
        type_="check",
    )
    op.drop_column("discovery_runs", "completeness_status")
    op.drop_column("discovery_runs", "is_complete_snapshot")
    op.drop_column("discovery_runs", "coverage_key")
