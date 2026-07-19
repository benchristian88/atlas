"""Add Knowledge Completeness Foundation v1.

Revision ID: 20260720_0012
Revises: 20260719_0011
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0012"
down_revision: str | None = "20260719_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID_DEFAULT = sa.text("gen_random_uuid()")

PERMISSIONS = {
    "knowledge_requirements.view": ("View knowledge requirements", "Knowledge completeness"),
    "knowledge_requirements.manage": ("Manage knowledge requirements", "Knowledge completeness"),
    "knowledge_gaps.view": ("View knowledge gaps", "Knowledge completeness"),
    "knowledge_gaps.defer": ("Defer knowledge gaps", "Knowledge completeness"),
    "knowledge_gaps.exception": ("Create knowledge-gap exceptions", "Knowledge completeness"),
    "knowledge_gaps.assign": ("Assign knowledge gaps", "Knowledge completeness"),
    "knowledge_completeness.evaluate": ("Evaluate knowledge completeness", "Knowledge completeness"),
}


def upgrade() -> None:
    op.create_table(
        "knowledge_requirement_definitions",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("key", sa.String(150), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("entity_type", sa.String(50), nullable=False, server_default="asset"),
        sa.Column("asset_type_id", UUID),
        sa.Column("requirement_level", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("rule_type", sa.String(80), nullable=False),
        sa.Column("rule_config_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("system_defined", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("remediation_hint", sa.Text()),
        sa.Column("configuration_valid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("configuration_error", sa.Text()),
        sa.Column("created_by_user_id", UUID),
        sa.Column("updated_by_user_id", UUID),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["asset_type_id"], ["asset_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("entity_type IN ('asset')", name="ck_knowledge_requirement_definitions_supported_entity_type"),
        sa.CheckConstraint("requirement_level IN ('required', 'conditional', 'recommended')", name="ck_knowledge_requirement_definitions_valid_requirement_level"),
        sa.CheckConstraint("severity IN ('critical', 'high', 'medium', 'low')", name="ck_knowledge_requirement_definitions_valid_severity"),
        sa.UniqueConstraint("key", name="uq_knowledge_requirement_definitions_key"),
    )
    for column in ("key", "entity_type", "asset_type_id", "requirement_level", "severity", "rule_type", "active", "configuration_valid", "created_by_user_id", "updated_by_user_id"):
        op.create_index(f"ix_knowledge_requirement_definitions_{column}", "knowledge_requirement_definitions", [column])

    op.create_table(
        "knowledge_gaps",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("requirement_definition_id", UUID, nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", UUID, nullable=False),
        sa.Column("asset_type_id_snapshot", UUID),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("requirement_level", sa.String(30), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details_json", JSONB),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_state_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by_user_id", UUID),
        sa.Column("resolution_reason", sa.Text()),
        sa.Column("exception_reason", sa.Text()),
        sa.Column("exception_created_at", sa.DateTime(timezone=True)),
        sa.Column("exception_created_by_user_id", UUID),
        sa.Column("exception_expires_at", sa.DateTime(timezone=True)),
        sa.Column("deferred_until", sa.DateTime(timezone=True)),
        sa.Column("deferred_by_user_id", UUID),
        sa.Column("assigned_to_user_id", UUID),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requirement_definition_id"], ["knowledge_requirement_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["asset_type_id_snapshot"], ["asset_types.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["exception_created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deferred_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id", "site_id"], ["sites.customer_id", "sites.id"], name="fk_knowledge_gaps_customer_site_sites", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('open', 'deferred', 'exception', 'resolved', 'superseded')", name="ck_knowledge_gaps_valid_status"),
        sa.CheckConstraint("requirement_level IN ('required', 'conditional', 'recommended')", name="ck_knowledge_gaps_valid_requirement_level"),
        sa.CheckConstraint("severity IN ('critical', 'high', 'medium', 'low')", name="ck_knowledge_gaps_valid_severity"),
    )
    for column in ("customer_id", "site_id", "requirement_definition_id", "entity_type", "entity_id", "asset_type_id_snapshot", "status", "severity", "requirement_level", "last_evaluated_at", "resolved_by_user_id", "exception_created_by_user_id", "exception_expires_at", "deferred_until", "deferred_by_user_id", "assigned_to_user_id"):
        op.create_index(f"ix_knowledge_gaps_{column}", "knowledge_gaps", [column])
    op.create_index("uq_knowledge_gaps_active_requirement_entity", "knowledge_gaps", ["requirement_definition_id", "entity_type", "entity_id"], unique=True, postgresql_where=sa.text("status IN ('open', 'deferred', 'exception')"))

    op.create_table(
        "knowledge_completeness_summaries",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", UUID, nullable=False),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("required_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_satisfied", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recommended_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recommended_satisfied", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_gap_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("high_gap_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_gap_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("exception_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completeness_status", sa.String(40), nullable=False, server_default="not_evaluated"),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id", "site_id"], ["sites.customer_id", "sites.id"], name="fk_completeness_summaries_customer_site_sites", ondelete="RESTRICT"),
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_completeness_entity"),
        sa.CheckConstraint("completeness_status IN ('not_evaluated', 'complete', 'operationally_complete', 'incomplete', 'critical_gaps', 'exception_accepted')", name="ck_knowledge_completeness_summaries_valid_completeness_status"),
    )
    for column in ("entity_type", "entity_id", "customer_id", "site_id", "completeness_status", "last_evaluated_at"):
        op.create_index(f"ix_knowledge_completeness_summaries_{column}", "knowledge_completeness_summaries", [column])

    permission_table = sa.table("permissions", sa.column("key", sa.String()), sa.column("name", sa.String()), sa.column("description", sa.String()), sa.column("category", sa.String()), sa.column("system_defined", sa.Boolean()))
    for key, (name, category) in PERMISSIONS.items():
        op.execute(postgresql.insert(permission_table).values(key=key, name=name, description=f"Built-in {name.lower()} permission.", category=category, system_defined=True).on_conflict_do_nothing(index_elements=["key"]))
        role_names = ["Master Administrator"]
        if key != "knowledge_requirements.manage":
            role_names.append("Administrator")
        if key not in {"knowledge_requirements.view", "knowledge_requirements.manage"}:
            role_names.append("Customer Administrator")
        if key in {"knowledge_gaps.view", "knowledge_requirements.view"}:
            role_names.append("Viewer")
        for role_name in role_names:
            op.execute(sa.text("""INSERT INTO role_permissions (role_id, permission_id) SELECT roles.id, permissions.id FROM roles, permissions WHERE roles.name = :role_name AND permissions.key = :permission_key ON CONFLICT (role_id, permission_id) DO NOTHING""").bindparams(role_name=role_name, permission_key=key))


def downgrade() -> None:
    # Permission keys are module constants, not external input.
    quoted_keys = ", ".join(f"'{key}'" for key in PERMISSIONS)
    op.execute(f"DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key IN ({quoted_keys}))")
    op.execute(f"DELETE FROM permissions WHERE key IN ({quoted_keys})")
    op.drop_table("knowledge_completeness_summaries")
    op.drop_table("knowledge_gaps")
    op.drop_table("knowledge_requirement_definitions")
