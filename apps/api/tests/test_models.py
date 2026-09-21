import importlib
from unittest.mock import Mock

from app.models import Base


EXPECTED_TABLES = {
    "users",
    "roles",
    "permissions",
    "role_permissions",
    "access_assignments",
    "workspaces",
    "customers",
    "sites",
    "integrations",
    "discovery_runs",
    "data_sources",
    "entity_source_links",
    "evidence_records",
    "knowledge_assertions",
    "reconciliation_items",
    "run_observed_entities",
    "knowledge_changes",
    "knowledge_requirement_definitions",
    "knowledge_gaps",
    "knowledge_completeness_summaries",
    "asset_types",
    "asset_categories",
    "relationship_types",
    "relationship_type_applicabilities",
    "service_types",
    "criticality_levels",
    "services",
    "service_asset_dependencies",
    "service_dependencies",
    "dependency_groups",
    "dependency_group_memberships",
    "business_functions",
    "service_business_functions",
    "assets",
    "asset_icon_cache",
    "asset_relationships",
    "networks",
    "asset_interfaces",
    "asset_facts",
    "custom_field_definitions",
    "custom_field_asset_types",
    "custom_field_options",
    "asset_custom_field_values",
    "documents",
    "audit_events",
    "system_settings",
}


CRITICAL_COLUMNS = {
    "users": {
        "id", "email", "password_hash", "display_name", "is_active",
        "force_password_change", "last_login_at", "failed_login_count",
        "locked_until", "session_version", "auth_provider", "external_subject",
        "mfa_enabled", "accent_colour", "theme_mode", "created_at", "updated_at",
    },
    "access_assignments": {
        "id", "user_id", "role_id", "scope_type", "customer_id", "site_id",
        "created_at", "updated_at",
    },
    "asset_categories": {
        "id", "key", "name", "description", "sort_order", "active",
        "show_in_topology", "icon_key", "accent_key", "created_at", "updated_at",
    },
    "asset_types": {
        "id", "key", "name", "description", "category", "category_id", "default_icon_url",
        "system_defined", "active", "sort_order", "created_at", "updated_at",
    },
    "relationship_types": {
        "id", "key", "name", "description", "source_label", "target_label",
        "inverse_label", "directional", "system_defined", "active", "sort_order",
        "allowed_source_asset_type_keys", "allowed_target_asset_type_keys",
        "created_at", "updated_at",
    },
    "assets": {
        "id", "workspace_id", "customer_id", "site_id", "source_integration_id",
        "external_id", "name", "asset_type", "icon_url", "vendor", "model",
        "hostname", "ip_address", "status", "description", "source", "metadata",
        "first_seen_at", "last_seen_at", "created_at", "updated_at",
    },
    "asset_relationships": {
        "id", "source_asset_id", "target_asset_id", "customer_id", "site_id",
        "relationship_type", "legacy_cross_context", "notes", "metadata",
        "created_at", "updated_at",
    },
    "dependency_groups": {
        "id", "customer_id", "site_id", "service_id", "supersedes_group_id",
        "name", "strategy", "requirement", "failure_effect", "valid_from",
        "valid_to", "created_by_user_id", "ended_by_user_id", "created_at",
        "updated_at",
    },
    "dependency_group_memberships": {
        "id", "dependency_group_id", "service_asset_dependency_id",
        "service_dependency_id", "valid_from", "valid_to",
        "created_by_user_id", "ended_by_user_id", "created_at", "updated_at",
    },
    "custom_field_definitions": {
        "id", "key", "name", "description", "help_text", "data_type", "required",
        "active", "sort_order", "applies_to_all_asset_types", "created_at", "updated_at",
    },
    "asset_custom_field_values": {
        "id", "asset_id", "field_definition_id", "value_text", "value_number",
        "value_date", "value_bool", "value_option_id", "created_at", "updated_at",
    },
    "audit_events": {
        "id", "workspace_id", "user_id", "actor_email", "actor_display_name",
        "event_type", "target_type", "target_id", "customer_id", "site_id",
        "success", "summary", "source_ip", "request_id", "metadata", "created_at",
    },
    "run_observed_entities": {
        "id", "discovery_run_id", "data_source_id", "customer_id", "site_id",
        "coverage_key", "entity_type", "external_id", "entity_id",
        "evidence_record_id", "observed_at", "created_at",
    },
    "knowledge_changes": {
        "id", "customer_id", "site_id", "change_type", "entity_type",
        "entity_id", "entity_name_snapshot", "predicate", "previous_value_json",
        "new_value_json", "truth_classification", "data_source_id",
        "discovery_run_id", "assertion_id", "reconciliation_item_id",
        "actor_user_id", "summary", "occurred_at", "metadata_json", "created_at",
    },
    "knowledge_assertions": {
        "id", "customer_id", "site_id", "subject_type", "subject_id",
        "subject_external_id", "predicate", "value_json", "object_type",
        "object_id", "object_external_id", "truth_classification",
        "confirmation_status", "data_source_id", "discovery_run_id",
        "evidence_record_id", "confidence", "first_observed_at",
        "last_observed_at", "valid_from", "valid_to", "superseded_by_id",
        "is_current", "is_source_current", "is_accepted", "accepted_at",
        "accepted_by_user_id", "retracted_at", "retracted_by_user_id",
        "retraction_reason", "created_at", "updated_at",
    },
    "knowledge_requirement_definitions": {
        "id", "key", "name", "description", "entity_type", "asset_type_id", "service_type_id",
        "requirement_level", "severity", "rule_type", "rule_config_json",
        "active", "system_defined", "sort_order", "remediation_hint",
        "configuration_valid", "configuration_error", "created_by_user_id",
        "updated_by_user_id", "created_at", "updated_at",
    },
    "knowledge_gaps": {
        "id", "customer_id", "site_id", "requirement_definition_id",
        "entity_type", "entity_id", "asset_type_id_snapshot", "status",
        "severity", "requirement_level", "summary", "details_json",
        "first_detected_at", "last_evaluated_at", "last_state_changed_at",
        "resolved_at", "resolved_by_user_id", "resolution_reason",
        "exception_reason", "exception_created_at",
        "exception_created_by_user_id", "exception_expires_at",
        "deferred_until", "deferred_by_user_id", "assigned_to_user_id",
        "created_at", "updated_at",
    },
    "knowledge_completeness_summaries": {
        "id", "entity_type", "entity_id", "customer_id", "site_id",
        "required_total", "required_satisfied", "recommended_total",
        "recommended_satisfied", "critical_gap_count", "high_gap_count",
        "open_gap_count", "exception_count", "completeness_status",
        "last_evaluated_at", "created_at", "updated_at",
    },
    "services": {
        "id", "customer_id", "site_id", "name", "slug", "description", "purpose",
        "service_type_id", "criticality_level_id", "lifecycle_status",
        "operational_status", "owner_name", "technical_contact", "support_group",
        "documentation_url", "runbook_url", "rto_minutes", "rpo_minutes",
        "backup_notes", "recovery_notes", "notes", "source", "created_by_user_id",
        "updated_by_user_id", "archived_at", "archived_by_user_id", "archive_reason", "deleted_at",
        "created_at", "updated_at",
    },
}


def test_assertion_acceptance_migration_is_additive_and_backfills_conservatively(
    monkeypatch,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260719_0011_assertion_acceptance_rollup"
    )
    assert migration.down_revision == "20260719_0010"
    operation = Mock()
    monkeypatch.setattr(migration, "op", operation)

    migration.upgrade()

    added = [call.args[1].name for call in operation.add_column.call_args_list]
    assert added == [
        "is_source_current",
        "is_accepted",
        "accepted_at",
        "accepted_by_user_id",
    ]
    executed = "\n".join(str(call.args[0]) for call in operation.execute.call_args_list)
    assert "is_source_current = is_current" in executed
    assert "HAVING count(*) = 1" in executed
    assert "confirmation_status = 'confirmed'" in executed
    assert "DELETE FROM evidence_records" not in executed
    assert not operation.drop_table.called
    assert any(
        call.args[0] == "uq_knowledge_assertions_single_accepted"
        and call.kwargs.get("unique") is True
        for call in operation.create_index.call_args_list
    )


def test_models_include_access_administration_and_enrichment_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    for table_name, expected_columns in CRITICAL_COLUMNS.items():
        assert set(Base.metadata.tables[table_name].columns.keys()) == expected_columns


def test_knowledge_completeness_ids_and_active_gap_uniqueness_follow_postgres_convention() -> None:
    for table_name in (
        "knowledge_requirement_definitions",
        "knowledge_gaps",
        "knowledge_completeness_summaries",
    ):
        column = Base.metadata.tables[table_name].c.id
        assert column.primary_key
        assert "gen_random_uuid" in str(column.server_default.arg)
    gaps = Base.metadata.tables["knowledge_gaps"]
    active_index = next(index for index in gaps.indexes if index.name == "uq_knowledge_gaps_active_requirement_entity")
    assert active_index.unique
    assert "open" in str(active_index.dialect_options["postgresql"]["where"])


def test_c1_service_models_use_postgres_uuid_defaults_and_guard_active_edges() -> None:
    for table_name in (
        "service_types", "criticality_levels", "services",
        "service_asset_dependencies", "service_dependencies",
        "business_functions", "service_business_functions",
        "relationship_type_applicabilities",
    ):
        column = Base.metadata.tables[table_name].c.id
        assert column.primary_key
        assert "gen_random_uuid" in str(column.server_default.arg)
    for table_name, index_name in (
        ("service_asset_dependencies", "uq_service_asset_dependencies_active_edge"),
        ("service_dependencies", "uq_service_dependencies_active_edge"),
        ("service_business_functions", "uq_service_business_functions_active_link"),
    ):
        index = next(item for item in Base.metadata.tables[table_name].indexes if item.name == index_name)
        assert index.unique
        assert "valid_to IS NULL" in str(index.dialect_options["postgresql"]["where"])


def test_asset_ownership_and_type_constraints_are_declared() -> None:
    assets = Base.metadata.tables["assets"]
    assert assets.c.site_id.nullable is False
    foreign_key_targets = {foreign_key.target_fullname for foreign_key in assets.foreign_keys}
    assert "asset_types.key" in foreign_key_targets
    assert "sites.id" in foreign_key_targets


def test_integration_ownership_requires_a_customer_site_pair() -> None:
    integrations = Base.metadata.tables["integrations"]
    assert integrations.c.site_id.nullable is False
    composite_targets = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in integrations.foreign_key_constraints
    }
    assert ("sites.customer_id", "sites.id") in composite_targets


def test_site_specific_network_ownership_requires_a_customer_site_pair() -> None:
    networks = Base.metadata.tables["networks"]
    assert networks.c.site_id.nullable is True
    composite_targets = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in networks.foreign_key_constraints
    }
    assert ("sites.customer_id", "sites.id") in composite_targets


def test_entity_source_links_are_unique_and_customer_site_safe() -> None:
    links = Base.metadata.tables["entity_source_links"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in links.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("data_source_id", "entity_type", "external_id") in unique_columns
    composite_targets = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in links.foreign_key_constraints
    }
    assert ("assets.id", "assets.customer_id", "assets.site_id") in composite_targets


def test_knowledge_v2_models_use_atlas_uuid_server_defaults() -> None:
    for table_name in ("run_observed_entities", "knowledge_changes"):
        id_column = Base.metadata.tables[table_name].c.id
        assert id_column.primary_key is True
        assert id_column.nullable is False
        assert id_column.server_default is not None
        assert str(id_column.server_default.arg).lower() == "gen_random_uuid()"

    observations = Base.metadata.tables["run_observed_entities"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in observations.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("discovery_run_id", "entity_type", "external_id") in unique_columns


def test_uuid_default_repair_migration_is_additive(monkeypatch) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260719_0010_fix_knowledge_uuid_defaults"
    )
    assert migration.down_revision == "20260719_0009"
    operation = Mock()
    monkeypatch.setattr(migration, "op", operation)

    migration.upgrade()

    assert [call.args[:2] for call in operation.alter_column.call_args_list] == [
        ("run_observed_entities", "id"),
        ("knowledge_changes", "id"),
    ]
    assert all(
        str(call.kwargs["server_default"]).lower() == "gen_random_uuid()"
        for call in operation.alter_column.call_args_list
    )
    assert all(
        call.kwargs["existing_nullable"] is False
        for call in operation.alter_column.call_args_list
    )


def test_case_insensitive_identity_and_type_name_indexes_are_declared() -> None:
    assert "uq_users_email_lower" in {
        index.name for index in Base.metadata.tables["users"].indexes
    }
    assert "uq_asset_types_name_lower" in {
        index.name for index in Base.metadata.tables["asset_types"].indexes
    }


def test_accent_colour_migration_is_nullable_and_preserves_existing_users(
    monkeypatch,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260717_0005_user_accent_colour"
    )
    operation = Mock()
    monkeypatch.setattr(migration, "op", operation)
    migration.upgrade()
    table_name, column = operation.add_column.call_args.args
    assert table_name == "users"
    assert column.name == "accent_colour"
    assert column.nullable is True
    assert "uq_relationship_types_name_lower" in {
        index.name for index in Base.metadata.tables["relationship_types"].indexes
    }


def test_relationships_preserve_context_and_use_restrictive_endpoints() -> None:
    table = Base.metadata.tables["asset_relationships"]
    assert table.c.customer_id.nullable is False
    assert table.c.site_id.nullable is False
    assert table.c.legacy_cross_context.nullable is False
    endpoint_foreign_keys = {
        foreign_key.parent.name: foreign_key.ondelete
        for foreign_key in table.foreign_keys
        if foreign_key.parent.name in {"source_asset_id", "target_asset_id"}
    }
    assert endpoint_foreign_keys == {
        "source_asset_id": "RESTRICT",
        "target_asset_id": "RESTRICT",
    }
    composite_targets = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in table.foreign_key_constraints
    }
    assert ("sites.customer_id", "sites.id") in composite_targets


def test_custom_values_have_exactly_one_typed_value_constraint() -> None:
    table = Base.metadata.tables["asset_custom_field_values"]
    constraints = {constraint.name for constraint in table.constraints}
    assert "ck_asset_custom_field_values_exactly_one_typed_value" in constraints
