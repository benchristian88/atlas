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
    "evidence_records",
    "knowledge_assertions",
    "reconciliation_items",
    "asset_types",
    "relationship_types",
    "assets",
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
        "mfa_enabled", "accent_colour", "created_at", "updated_at",
    },
    "access_assignments": {
        "id", "user_id", "role_id", "scope_type", "customer_id", "site_id",
        "created_at", "updated_at",
    },
    "asset_types": {
        "id", "key", "name", "description", "category", "default_icon_url",
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
}


def test_models_include_access_administration_and_enrichment_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    for table_name, expected_columns in CRITICAL_COLUMNS.items():
        assert set(Base.metadata.tables[table_name].columns.keys()) == expected_columns


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
