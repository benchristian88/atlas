from app.models import Base


EXPECTED_COLUMNS = {
    "users": {"id", "email", "password_hash", "display_name", "created_at", "updated_at"},
    "workspaces": {"id", "name", "slug", "created_at", "updated_at"},
    "customers": {"id", "workspace_id", "name", "description", "status", "created_at", "updated_at"},
    "sites": {"id", "customer_id", "name", "address", "notes", "status", "created_at", "updated_at"},
    "integrations": {
        "id", "customer_id", "site_id", "plugin_id", "name", "base_url",
        "username_or_token_id", "secret_reference", "verify_tls", "status",
        "created_at", "updated_at",
    },
    "discovery_runs": {
        "id", "integration_id", "status", "started_at", "completed_at",
        "error_message", "raw_payload", "summary",
    },
    "assets": {
        "id", "workspace_id", "customer_id", "site_id", "source_integration_id",
        "external_id", "name", "asset_type", "vendor", "model", "hostname", "ip_address", "status", "description", "source",
        "metadata", "first_seen_at", "last_seen_at", "created_at", "updated_at",
    },
    "asset_relationships": {
        "id", "source_asset_id", "target_asset_id", "relationship_type", "notes", "metadata",
        "created_at", "updated_at",
    },
    "networks": {
        "id", "customer_id", "site_id", "name", "network_type", "vlan_id",
        "cidr", "gateway", "purpose", "zone", "notes", "created_at", "updated_at",
    },
    "asset_interfaces": {
        "id", "asset_id", "network_id", "name", "ip_address", "mac_address",
        "is_primary", "notes", "created_at", "updated_at",
    },
    "asset_facts": {"id", "asset_id", "key", "value", "source", "created_at", "updated_at"},
    "documents": {
        "id", "asset_id", "title", "content_markdown",
        "generated_from_discovery_run_id", "created_at", "updated_at",
    },
    "audit_events": {
        "id", "workspace_id", "user_id", "event_type", "target_type", "target_id",
        "metadata", "created_at",
    },
}


def test_models_match_documented_tables_and_columns() -> None:
    assert set(Base.metadata.tables) == set(EXPECTED_COLUMNS)
    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        assert set(Base.metadata.tables[table_name].columns.keys()) == expected_columns


def test_discovered_asset_identity_is_unique_per_integration() -> None:
    constraints = Base.metadata.tables["assets"].constraints
    column_sets = {
        tuple(constraint.columns.keys())
        for constraint in constraints
        if hasattr(constraint, "columns")
    }
    assert ("source_integration_id", "external_id") in column_sets
