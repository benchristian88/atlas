"""Add the C1 first-class homelab service model.

Revision ID: 20260720_0013
Revises: 20260720_0012
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0013"
down_revision: str | None = "20260720_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID_DEFAULT = sa.text("gen_random_uuid()")

PERMISSIONS = {
    "services.view": ("View services", "Services"),
    "services.create": ("Create services", "Services"),
    "services.edit": ("Edit services", "Services"),
    "services.archive": ("Archive services", "Services"),
    "service_dependencies.view": ("View service dependencies", "Services"),
    "service_dependencies.manage": ("Manage service dependencies", "Services"),
    "business_functions.view": ("View business functions", "Business functions"),
    "business_functions.manage": ("Manage business functions", "Business functions"),
    "service_types.view": ("View service types", "Reference data"),
    "service_types.manage": ("Manage service types", "Reference data"),
    "criticality_levels.view": ("View criticality levels", "Reference data"),
    "criticality_levels.manage": ("Manage criticality levels", "Reference data"),
    "service_completeness.evaluate": ("Evaluate service completeness", "Knowledge completeness"),
}

SERVICE_TYPES = (
    ("application_service", "Application Service", True),
    ("infrastructure_service", "Infrastructure Service", True),
    ("platform_service", "Platform Service", True),
    ("shared_service", "Shared Service", True),
    ("external_service", "External Service", False),
    ("database_service", "Database Service", True),
    ("integration_service", "Integration Service", True),
    ("business_service", "Business Service", True),
)

CRITICALITY_LEVELS = (
    ("critical", "Critical", 100, 60, 15),
    ("high", "High", 75, 240, 60),
    ("medium", "Medium", 50, 1440, 720),
    ("low", "Low", 25, 4320, 1440),
)

SERVICE_REQUIREMENTS = (
    ("service_name", "Name", "required", "critical", "service_field_present", '{"field":"name"}', 10, "Give the Service a clear name."),
    ("service_type", "Service type", "required", "critical", "service_field_present", '{"field":"service_type_id"}', 20, "Choose the operational Service type."),
    ("service_purpose", "Purpose", "required", "high", "service_field_present", '{"field":"purpose"}', 30, "Describe what capability the Service provides."),
    ("service_criticality", "Criticality", "required", "high", "service_field_present", '{"field":"criticality_level_id"}', 40, "Choose a criticality level."),
    ("service_asset_dependency", "Asset dependency", "required", "high", "service_asset_dependency_exists", '{"minimum":1}', 50, "Link the Service to the Asset it runs on or uses."),
    ("service_owner", "Owner", "recommended", "medium", "service_field_present", '{"field":"owner_name"}', 100, "Record who owns this Service."),
    ("service_contact", "Technical contact or support group", "recommended", "medium", "one_of", '{"rules":[{"rule_type":"service_field_present","rule_config":{"field":"technical_contact"}},{"rule_type":"service_field_present","rule_config":{"field":"support_group"}}]}', 110, "Record a technical contact or support group."),
    ("service_rto", "Recovery time objective", "recommended", "medium", "service_field_present", '{"field":"rto_minutes"}', 120, "Define an RTO."),
    ("service_rpo", "Recovery point objective", "recommended", "medium", "service_field_present", '{"field":"rpo_minutes"}', 130, "Define an RPO."),
    ("service_recovery_guidance", "Recovery guidance", "recommended", "medium", "one_of", '{"rules":[{"rule_type":"service_field_present","rule_config":{"field":"recovery_notes"}},{"rule_type":"service_field_present","rule_config":{"field":"runbook_url"}}]}', 140, "Add recovery notes or a runbook URL."),
    ("service_business_function", "Business function", "recommended", "low", "service_business_function_exists", '{"minimum":1}', 150, "Link the Service to a Business Function."),
    ("critical_service_rto", "Critical-service RTO", "conditional", "critical", "service_field_present", '{"field":"rto_minutes","applicable_criticality_rank_min":75}', 200, "High and Critical Services require an RTO."),
    ("critical_service_rpo", "Critical-service RPO", "conditional", "critical", "service_field_present", '{"field":"rpo_minutes","applicable_criticality_rank_min":75}', 210, "High and Critical Services require an RPO."),
    ("critical_service_owner", "Critical-service owner", "conditional", "high", "service_field_present", '{"field":"owner_name","applicable_criticality_rank_min":75}', 220, "High and Critical Services require an owner."),
    ("critical_service_contact", "Critical-service contact", "conditional", "high", "one_of", '{"applicable_criticality_rank_min":75,"rules":[{"rule_type":"service_field_present","rule_config":{"field":"technical_contact"}},{"rule_type":"service_field_present","rule_config":{"field":"support_group"}}]}', 230, "High and Critical Services require a contact or support group."),
    ("critical_service_recovery", "Critical-service recovery guidance", "conditional", "high", "one_of", '{"applicable_criticality_rank_min":75,"rules":[{"rule_type":"service_field_present","rule_config":{"field":"recovery_notes"}},{"rule_type":"service_field_present","rule_config":{"field":"runbook_url"}}]}', 240, "High and Critical Services require recovery guidance."),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "service_types",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("icon_key", sa.String(100)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("system_defined", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("requires_asset_dependency", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", UUID),
        sa.Column("updated_by_user_id", UUID),
        *_timestamps(),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("key", name="uq_service_types_key"),
    )
    op.create_index("uq_service_types_name_lower", "service_types", [sa.text("lower(name)")], unique=True)
    for column in ("key", "active", "sort_order", "created_by_user_id", "updated_by_user_id"):
        op.create_index(f"ix_service_types_{column}", "service_types", [column])

    op.create_table(
        "criticality_levels",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("default_rto_minutes", sa.Integer()),
        sa.Column("default_rpo_minutes", sa.Integer()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("system_defined", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        *_timestamps(),
        sa.CheckConstraint("default_rto_minutes IS NULL OR default_rto_minutes >= 0", name="ck_criticality_levels_valid_default_rto"),
        sa.CheckConstraint("default_rpo_minutes IS NULL OR default_rpo_minutes >= 0", name="ck_criticality_levels_valid_default_rpo"),
        sa.UniqueConstraint("key", name="uq_criticality_levels_key"),
    )
    op.create_index("uq_criticality_levels_name_lower", "criticality_levels", [sa.text("lower(name)")], unique=True)
    for column in ("key", "rank", "active", "sort_order"):
        op.create_index(f"ix_criticality_levels_{column}", "criticality_levels", [column])

    op.create_table(
        "services",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("purpose", sa.Text()),
        sa.Column("service_type_id", UUID, nullable=False),
        sa.Column("criticality_level_id", UUID, nullable=False),
        sa.Column("lifecycle_status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("operational_status", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("owner_name", sa.String(255)),
        sa.Column("technical_contact", sa.String(255)),
        sa.Column("support_group", sa.String(255)),
        sa.Column("documentation_url", sa.String(2048)),
        sa.Column("runbook_url", sa.String(2048)),
        sa.Column("rto_minutes", sa.Integer()),
        sa.Column("rpo_minutes", sa.Integer()),
        sa.Column("backup_notes", sa.Text()),
        sa.Column("recovery_notes", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("created_by_user_id", UUID),
        sa.Column("updated_by_user_id", UUID),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("archived_by_user_id", UUID),
        sa.Column("archive_reason", sa.Text()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id", "site_id"], ["sites.customer_id", "sites.id"], name="fk_services_customer_site_sites", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_type_id"], ["service_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["criticality_level_id"], ["criticality_levels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["archived_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("rto_minutes IS NULL OR rto_minutes >= 0", name="ck_services_valid_rto_minutes"),
        sa.CheckConstraint("rpo_minutes IS NULL OR rpo_minutes >= 0", name="ck_services_valid_rpo_minutes"),
    )
    for column in ("customer_id", "site_id", "name", "slug", "service_type_id", "criticality_level_id", "lifecycle_status", "operational_status", "source", "created_by_user_id", "updated_by_user_id", "archived_at", "archived_by_user_id"):
        op.create_index(f"ix_services_{column}", "services", [column])
    op.create_index("uq_services_customer_name_without_site", "services", ["customer_id", sa.text("lower(name)")], unique=True, postgresql_where=sa.text("site_id IS NULL AND archived_at IS NULL"))
    op.create_index("uq_services_customer_site_name", "services", ["customer_id", "site_id", sa.text("lower(name)")], unique=True, postgresql_where=sa.text("site_id IS NOT NULL AND archived_at IS NULL"))
    op.create_index("uq_services_customer_slug_without_site", "services", ["customer_id", "slug"], unique=True, postgresql_where=sa.text("site_id IS NULL AND archived_at IS NULL"))
    op.create_index("uq_services_customer_site_slug", "services", ["customer_id", "site_id", "slug"], unique=True, postgresql_where=sa.text("site_id IS NOT NULL AND archived_at IS NULL"))

    op.create_table(
        "business_functions",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner_name", sa.String(255)),
        sa.Column("criticality_level_id", UUID),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", UUID),
        sa.Column("updated_by_user_id", UUID),
        *_timestamps(),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id", "site_id"], ["sites.customer_id", "sites.id"], name="fk_business_functions_customer_site_sites", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["criticality_level_id"], ["criticality_levels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("customer_id", "site_id", "name", "criticality_level_id", "active", "created_by_user_id", "updated_by_user_id"):
        op.create_index(f"ix_business_functions_{column}", "business_functions", [column])
    op.create_index("uq_business_functions_customer_name_without_site", "business_functions", ["customer_id", sa.text("lower(name)")], unique=True, postgresql_where=sa.text("site_id IS NULL"))
    op.create_index("uq_business_functions_customer_site_name", "business_functions", ["customer_id", "site_id", sa.text("lower(name)")], unique=True, postgresql_where=sa.text("site_id IS NOT NULL"))

    op.create_table(
        "relationship_type_applicabilities",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("relationship_type_id", UUID, nullable=False),
        sa.Column("source_entity_type", sa.String(50), nullable=False),
        sa.Column("target_entity_type", sa.String(50), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["relationship_type_id"], ["relationship_types.id"], ondelete="CASCADE"),
        sa.CheckConstraint("source_entity_type IN ('asset', 'service', 'business_function')", name="ck_relationship_type_applicabilities_valid_source_entity_type"),
        sa.CheckConstraint("target_entity_type IN ('asset', 'service', 'business_function')", name="ck_relationship_type_applicabilities_valid_target_entity_type"),
        sa.UniqueConstraint("relationship_type_id", "source_entity_type", "target_entity_type", name="uq_relationship_type_applicability_endpoints"),
    )
    for column in ("relationship_type_id", "source_entity_type", "target_entity_type", "active"):
        op.create_index(f"ix_relationship_type_applicabilities_{column}", "relationship_type_applicabilities", [column])

    dependency_columns = [
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("relationship_type_id", UUID, nullable=False),
        sa.Column("required_for_operation", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("description", sa.Text()),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", UUID),
        sa.Column("updated_by_user_id", UUID),
        sa.Column("ended_by_user_id", UUID),
    ]
    op.create_table(
        "service_asset_dependencies",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("service_id", UUID, nullable=False),
        sa.Column("asset_id", UUID, nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        *dependency_columns,
        *_timestamps(),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id", "site_id"], ["sites.customer_id", "sites.id"], name="fk_service_asset_dependencies_customer_site_sites", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["relationship_type_id"], ["relationship_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ended_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("uq_service_asset_dependencies_active_edge", "service_asset_dependencies", ["service_id", "asset_id", "relationship_type_id"], unique=True, postgresql_where=sa.text("valid_to IS NULL"))
    for column in ("service_id", "asset_id", "customer_id", "site_id", "relationship_type_id", "valid_to", "created_by_user_id", "updated_by_user_id", "ended_by_user_id"):
        op.create_index(f"ix_service_asset_dependencies_{column}", "service_asset_dependencies", [column])

    op.create_table(
        "service_dependencies",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("source_service_id", UUID, nullable=False),
        sa.Column("target_service_id", UUID, nullable=False),
        *[column.copy() for column in dependency_columns],
        *_timestamps(),
        sa.ForeignKeyConstraint(["source_service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id", "site_id"], ["sites.customer_id", "sites.id"], name="fk_service_dependencies_customer_site_sites", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["relationship_type_id"], ["relationship_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ended_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("source_service_id <> target_service_id", name="ck_service_dependencies_not_self_referential"),
    )
    op.create_index("uq_service_dependencies_active_edge", "service_dependencies", ["source_service_id", "target_service_id", "relationship_type_id"], unique=True, postgresql_where=sa.text("valid_to IS NULL"))
    for column in ("source_service_id", "target_service_id", "customer_id", "site_id", "relationship_type_id", "valid_to", "created_by_user_id", "updated_by_user_id", "ended_by_user_id"):
        op.create_index(f"ix_service_dependencies_{column}", "service_dependencies", [column])

    op.create_table(
        "service_business_functions",
        sa.Column("id", UUID, primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("service_id", UUID, nullable=False),
        sa.Column("business_function_id", UUID, nullable=False),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("relationship_type_id", UUID),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("importance", sa.String(100)),
        sa.Column("description", sa.Text()),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", UUID),
        sa.Column("ended_by_user_id", UUID),
        *_timestamps(),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["business_function_id"], ["business_functions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id", "site_id"], ["sites.customer_id", "sites.id"], name="fk_service_business_functions_customer_site_sites", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["relationship_type_id"], ["relationship_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ended_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("uq_service_business_functions_active_link", "service_business_functions", ["service_id", "business_function_id"], unique=True, postgresql_where=sa.text("valid_to IS NULL"))
    for column in ("service_id", "business_function_id", "customer_id", "site_id", "relationship_type_id", "valid_to", "created_by_user_id", "ended_by_user_id"):
        op.create_index(f"ix_service_business_functions_{column}", "service_business_functions", [column])

    op.drop_constraint("ck_knowledge_requirement_definitions_supported_entity_type", "knowledge_requirement_definitions", type_="check")
    op.add_column("knowledge_requirement_definitions", sa.Column("service_type_id", UUID))
    op.create_foreign_key("fk_knowledge_requirements_service_type", "knowledge_requirement_definitions", "service_types", ["service_type_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_knowledge_requirement_definitions_service_type_id", "knowledge_requirement_definitions", ["service_type_id"])
    op.create_check_constraint("ck_knowledge_requirement_definitions_supported_entity_type", "knowledge_requirement_definitions", "entity_type IN ('asset', 'service')")

    service_type_table = sa.table("service_types", sa.column("key", sa.String()), sa.column("name", sa.String()), sa.column("active", sa.Boolean()), sa.column("system_defined", sa.Boolean()), sa.column("sort_order", sa.Integer()), sa.column("requires_asset_dependency", sa.Boolean()))
    for index, (key, name, needs_asset) in enumerate(SERVICE_TYPES, start=10):
        op.execute(postgresql.insert(service_type_table).values(key=key, name=name, active=True, system_defined=True, sort_order=index, requires_asset_dependency=needs_asset).on_conflict_do_nothing(index_elements=["key"]))
    criticality_table = sa.table("criticality_levels", sa.column("key", sa.String()), sa.column("name", sa.String()), sa.column("rank", sa.Integer()), sa.column("default_rto_minutes", sa.Integer()), sa.column("default_rpo_minutes", sa.Integer()), sa.column("active", sa.Boolean()), sa.column("system_defined", sa.Boolean()), sa.column("sort_order", sa.Integer()))
    for index, (key, name, rank, rto, rpo) in enumerate(CRITICALITY_LEVELS, start=10):
        op.execute(postgresql.insert(criticality_table).values(key=key, name=name, rank=rank, default_rto_minutes=rto, default_rpo_minutes=rpo, active=True, system_defined=True, sort_order=index).on_conflict_do_nothing(index_elements=["key"]))

    safe_keys = ("related_to", "hosted_on", "runs_on", "connects_to", "depends_on", "uses_storage", "backs_up_to", "monitors", "proxies", "authenticates", "served_by", "protected_by")
    safe_keys_sql = ", ".join(f"'{key}'" for key in safe_keys)
    for source, target in (("service", "asset"), ("service", "service")):
        op.execute(f"INSERT INTO relationship_type_applicabilities (relationship_type_id, source_entity_type, target_entity_type, active) SELECT id, '{source}', '{target}', true FROM relationship_types WHERE key IN ({safe_keys_sql}) ON CONFLICT (relationship_type_id, source_entity_type, target_entity_type) DO NOTHING")

    requirements = sa.table("knowledge_requirement_definitions", sa.column("key", sa.String()), sa.column("name", sa.String()), sa.column("description", sa.Text()), sa.column("entity_type", sa.String()), sa.column("requirement_level", sa.String()), sa.column("severity", sa.String()), sa.column("rule_type", sa.String()), sa.column("rule_config_json", JSONB), sa.column("active", sa.Boolean()), sa.column("system_defined", sa.Boolean()), sa.column("sort_order", sa.Integer()), sa.column("remediation_hint", sa.Text()), sa.column("configuration_valid", sa.Boolean()))
    for key, name, level, severity, rule_type, raw_config, sort_order, hint in SERVICE_REQUIREMENTS:
        json_expression = sa.text(f"'{raw_config.replace(':', r'\:')}'::jsonb")
        op.execute(postgresql.insert(requirements).values(key=key, name=name, description=f"Default C1 Service knowledge requirement: {name}.", entity_type="service", requirement_level=level, severity=severity, rule_type=rule_type, rule_config_json=json_expression, active=True, system_defined=True, sort_order=sort_order, remediation_hint=hint, configuration_valid=True).on_conflict_do_nothing(index_elements=["key"]))

    permission_table = sa.table("permissions", sa.column("key", sa.String()), sa.column("name", sa.String()), sa.column("description", sa.Text()), sa.column("category", sa.String()), sa.column("system_defined", sa.Boolean()))
    for key, (name, category) in PERMISSIONS.items():
        op.execute(postgresql.insert(permission_table).values(key=key, name=name, description=f"Built-in {name.lower()} permission.", category=category, system_defined=True).on_conflict_do_nothing(index_elements=["key"]))
        roles = ["Master Administrator"]
        if key not in {"service_types.manage", "criticality_levels.manage"}:
            roles.append("Administrator")
        if key in {"services.view", "service_dependencies.view", "business_functions.view", "service_types.view", "criticality_levels.view"}:
            roles.extend(["Customer Administrator", "Viewer"])
        if key in {"services.create", "services.edit", "services.archive", "service_dependencies.manage", "business_functions.manage", "service_completeness.evaluate"}:
            roles.append("Customer Administrator")
        for role_name in set(roles):
            op.execute(sa.text("INSERT INTO role_permissions (role_id, permission_id) SELECT roles.id, permissions.id FROM roles, permissions WHERE roles.name = :role AND permissions.key = :permission ON CONFLICT (role_id, permission_id) DO NOTHING").bindparams(role=role_name, permission=key))


def downgrade() -> None:
    keys = ", ".join(f"'{key}'" for key in PERMISSIONS)
    op.execute(f"DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key IN ({keys}))")
    op.execute(f"DELETE FROM permissions WHERE key IN ({keys})")
    op.drop_constraint("ck_knowledge_requirement_definitions_supported_entity_type", "knowledge_requirement_definitions", type_="check")
    op.drop_index("ix_knowledge_requirement_definitions_service_type_id", table_name="knowledge_requirement_definitions")
    op.drop_constraint("fk_knowledge_requirements_service_type", "knowledge_requirement_definitions", type_="foreignkey")
    op.drop_column("knowledge_requirement_definitions", "service_type_id")
    op.create_check_constraint("ck_knowledge_requirement_definitions_supported_entity_type", "knowledge_requirement_definitions", "entity_type IN ('asset')")
    for table in ("service_business_functions", "service_dependencies", "service_asset_dependencies", "relationship_type_applicabilities", "business_functions", "services", "criticality_levels", "service_types"):
        op.drop_table(table)
