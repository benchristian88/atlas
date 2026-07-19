"""Separate source-current assertions from accepted Atlas knowledge.

Revision ID: 20260719_0011
Revises: 20260719_0010
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260719_0011"
down_revision: str | None = "20260719_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SINGLE_PREDICATES = (
    "name",
    "hostname",
    "asset_type",
    "status",
    "operational_state",
    "observation_state",
    "platform",
    "lifecycle_state",
)


def upgrade() -> None:
    op.add_column(
        "knowledge_assertions",
        sa.Column(
            "is_source_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "knowledge_assertions",
        sa.Column(
            "is_accepted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "knowledge_assertions",
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "knowledge_assertions",
        sa.Column("accepted_by_user_id", sa.UUID()),
    )
    op.create_foreign_key(
        "fk_knowledge_assertions_accepted_by_user_id_users",
        "knowledge_assertions",
        "users",
        ["accepted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_knowledge_assertions_is_source_current",
        "knowledge_assertions",
        ["is_source_current"],
    )
    op.create_index(
        "ix_knowledge_assertions_is_accepted",
        "knowledge_assertions",
        ["is_accepted"],
    )
    op.create_index(
        "ix_knowledge_assertions_accepted_by_user_id",
        "knowledge_assertions",
        ["accepted_by_user_id"],
    )

    # ``is_current`` historically meant latest from one source. Preserve that
    # state exactly and make the new name explicit.
    op.execute(
        "UPDATE knowledge_assertions SET is_source_current = is_current"
    )

    # Conservative backfill: accept only one confirmed, source-current
    # assertion that exactly matches an operational Asset scalar. Ambiguous
    # candidates remain unaccepted and are surfaced by the roll-up API.
    op.execute(
        """
        WITH candidates AS (
            SELECT ka.id, ka.subject_id, ka.predicate
            FROM knowledge_assertions ka
            JOIN assets a
              ON ka.subject_type = 'asset' AND ka.subject_id = a.id
            WHERE ka.is_source_current = true
              AND ka.retracted_at IS NULL
              AND ka.confirmation_status = 'confirmed'
              AND (
                (ka.predicate = 'name' AND ka.value_json = to_jsonb(a.name)) OR
                (ka.predicate = 'hostname' AND ka.value_json = to_jsonb(a.hostname)) OR
                (ka.predicate = 'asset_type' AND ka.value_json = to_jsonb(a.asset_type)) OR
                (ka.predicate = 'status' AND ka.value_json = to_jsonb(a.status))
              )
        ), unique_candidates AS (
            SELECT subject_id, predicate, min(id::text)::uuid AS assertion_id
            FROM candidates
            GROUP BY subject_id, predicate
            HAVING count(*) = 1
        )
        UPDATE knowledge_assertions ka
        SET is_accepted = true,
            accepted_at = COALESCE(ka.valid_from, ka.last_observed_at, ka.updated_at)
        FROM unique_candidates candidate
        WHERE ka.id = candidate.assertion_id
        """
    )

    predicate_sql = ", ".join(f"'{value}'" for value in SINGLE_PREDICATES)
    op.create_index(
        "uq_knowledge_assertions_single_accepted",
        "knowledge_assertions",
        ["subject_type", "subject_id", "predicate"],
        unique=True,
        postgresql_where=sa.text(
            "is_accepted = true AND retracted_at IS NULL "
            f"AND subject_id IS NOT NULL AND predicate IN ({predicate_sql})"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_knowledge_assertions_single_accepted",
        table_name="knowledge_assertions",
    )
    op.drop_index(
        "ix_knowledge_assertions_accepted_by_user_id",
        table_name="knowledge_assertions",
    )
    op.drop_index(
        "ix_knowledge_assertions_is_accepted",
        table_name="knowledge_assertions",
    )
    op.drop_index(
        "ix_knowledge_assertions_is_source_current",
        table_name="knowledge_assertions",
    )
    op.drop_constraint(
        "fk_knowledge_assertions_accepted_by_user_id_users",
        "knowledge_assertions",
        type_="foreignkey",
    )
    op.drop_column("knowledge_assertions", "accepted_by_user_id")
    op.drop_column("knowledge_assertions", "accepted_at")
    op.drop_column("knowledge_assertions", "is_accepted")
    op.drop_column("knowledge_assertions", "is_source_current")
