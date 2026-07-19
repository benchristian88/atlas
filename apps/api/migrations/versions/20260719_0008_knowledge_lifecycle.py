"""Add safe discovery-run and assertion lifecycle controls.

Revision ID: 20260719_0008
Revises: 20260719_0007
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0008"
down_revision: str | None = "20260719_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

PERMISSIONS = {
    "discovery_runs.archive": ("Archive and restore discovery runs", "Discovery"),
    "discovery_runs.delete": ("Safely delete unused discovery runs", "Discovery"),
    "assertions.retract": ("Retract knowledge assertions", "Knowledge"),
    "assertions.delete": ("Safely delete unused knowledge assertions", "Knowledge"),
}


def upgrade() -> None:
    op.add_column("discovery_runs", sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.add_column("discovery_runs", sa.Column("archived_by_user_id", UUID))
    op.add_column("discovery_runs", sa.Column("archive_reason", sa.Text()))
    op.create_foreign_key(
        "fk_discovery_runs_archived_by_user_id_users",
        "discovery_runs",
        "users",
        ["archived_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_discovery_runs_archived_at", "discovery_runs", ["archived_at"])
    op.create_index(
        "ix_discovery_runs_archived_by_user_id",
        "discovery_runs",
        ["archived_by_user_id"],
    )

    op.add_column("knowledge_assertions", sa.Column("retracted_at", sa.DateTime(timezone=True)))
    op.add_column("knowledge_assertions", sa.Column("retracted_by_user_id", UUID))
    op.add_column("knowledge_assertions", sa.Column("retraction_reason", sa.Text()))
    op.create_foreign_key(
        "fk_knowledge_assertions_retracted_by_user_id_users",
        "knowledge_assertions",
        "users",
        ["retracted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_knowledge_assertions_retracted_at",
        "knowledge_assertions",
        ["retracted_at"],
    )
    op.create_index(
        "ix_knowledge_assertions_retracted_by_user_id",
        "knowledge_assertions",
        ["retracted_by_user_id"],
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
        for role_name in (
            "Master Administrator",
            "Administrator",
            "Customer Administrator",
        ):
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
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            USING permissions
            WHERE role_permissions.permission_id = permissions.id
              AND permissions.key IN (
                'discovery_runs.archive', 'discovery_runs.delete',
                'assertions.retract', 'assertions.delete'
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE key IN (
              'discovery_runs.archive', 'discovery_runs.delete',
              'assertions.retract', 'assertions.delete'
            )
            """
        )
    )

    op.drop_index("ix_knowledge_assertions_retracted_by_user_id", table_name="knowledge_assertions")
    op.drop_index("ix_knowledge_assertions_retracted_at", table_name="knowledge_assertions")
    op.drop_constraint(
        "fk_knowledge_assertions_retracted_by_user_id_users",
        "knowledge_assertions",
        type_="foreignkey",
    )
    op.drop_column("knowledge_assertions", "retraction_reason")
    op.drop_column("knowledge_assertions", "retracted_by_user_id")
    op.drop_column("knowledge_assertions", "retracted_at")

    op.drop_index("ix_discovery_runs_archived_by_user_id", table_name="discovery_runs")
    op.drop_index("ix_discovery_runs_archived_at", table_name="discovery_runs")
    op.drop_constraint(
        "fk_discovery_runs_archived_by_user_id_users",
        "discovery_runs",
        type_="foreignkey",
    )
    op.drop_column("discovery_runs", "archive_reason")
    op.drop_column("discovery_runs", "archived_by_user_id")
    op.drop_column("discovery_runs", "archived_at")
