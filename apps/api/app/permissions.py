"""Built-in Atlas permission and role definitions.

The database is authoritative at runtime.  These constants are used only for
idempotent bootstrap/seed operations and for keeping permission names
consistent across route modules.
"""

from __future__ import annotations


PERMISSIONS: dict[str, tuple[str, str]] = {
    "users.view": ("View users", "Users"),
    "users.create": ("Create users", "Users"),
    "users.edit": ("Edit users", "Users"),
    "users.disable": ("Enable or disable users", "Users"),
    "users.assign_roles": ("Assign roles and access scopes", "Users"),
    "roles.view": ("View roles and permissions", "Roles"),
    "roles.manage": ("Manage roles and permissions", "Roles"),
    "customers.view": ("View customers", "Customers"),
    "customers.manage": ("Manage customers", "Customers"),
    "sites.view": ("View sites", "Sites"),
    "sites.manage": ("Manage sites", "Sites"),
    "assets.view": ("View assets", "Assets"),
    "assets.create": ("Create assets", "Assets"),
    "assets.edit": ("Edit assets", "Assets"),
    "assets.delete": ("Delete assets", "Assets"),
    "relationships.view": ("View relationships", "Relationships"),
    "relationships.create": ("Create relationships", "Relationships"),
    "relationships.edit": ("Edit relationships", "Relationships"),
    "relationships.delete": ("Delete relationships", "Relationships"),
    "networks.view": ("View networks and interfaces", "Networks"),
    "networks.create": ("Create networks and interfaces", "Networks"),
    "networks.edit": ("Edit networks and interfaces", "Networks"),
    "networks.delete": ("Delete networks and interfaces", "Networks"),
    "asset_types.view": ("View asset types", "Reference data"),
    "asset_types.manage": ("Manage asset types", "Reference data"),
    "relationship_types.view": ("View relationship types", "Reference data"),
    "relationship_types.manage": ("Manage relationship types", "Reference data"),
    "custom_fields.view": ("View custom-field definitions", "Reference data"),
    "custom_fields.manage": ("Manage custom-field definitions", "Reference data"),
    "audit.view": ("View audit events", "Audit"),
    "integrations.view": ("View integrations and discovery runs", "Integrations"),
    "integrations.manage": ("Manage integrations and discovery runs", "Integrations"),
    "discovery_runs.archive": ("Archive and restore discovery runs", "Discovery"),
    "discovery_runs.delete": ("Safely delete unused discovery runs", "Discovery"),
    "assertions.retract": ("Retract knowledge assertions", "Knowledge"),
    "assertions.delete": ("Safely delete unused knowledge assertions", "Knowledge"),
    "system_settings.manage": ("Manage system settings", "System"),
}


MASTER_ADMINISTRATOR = "Master Administrator"
ADMINISTRATOR = "Administrator"
CUSTOMER_ADMINISTRATOR = "Customer Administrator"
VIEWER = "Viewer"


ROLE_PERMISSION_KEYS: dict[str, set[str]] = {
    MASTER_ADMINISTRATOR: set(PERMISSIONS),
    ADMINISTRATOR: {
        key
        for key in PERMISSIONS
        if key not in {"roles.manage", "system_settings.manage"}
    },
    CUSTOMER_ADMINISTRATOR: {
        "customers.view",
        "customers.manage",
        "sites.view",
        "sites.manage",
        "assets.view",
        "assets.create",
        "assets.edit",
        "assets.delete",
        "relationships.view",
        "relationships.create",
        "relationships.edit",
        "relationships.delete",
        "networks.view",
        "networks.create",
        "networks.edit",
        "networks.delete",
        "asset_types.view",
        "relationship_types.view",
        "custom_fields.view",
        "integrations.view",
        "integrations.manage",
        "discovery_runs.archive",
        "discovery_runs.delete",
        "assertions.retract",
        "assertions.delete",
    },
    VIEWER: {
        "customers.view",
        "sites.view",
        "assets.view",
        "relationships.view",
        "networks.view",
        "asset_types.view",
        "relationship_types.view",
        "custom_fields.view",
        "integrations.view",
    },
}
