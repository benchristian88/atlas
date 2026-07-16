# Atlas data model v0

## Entity relationships

```mermaid
erDiagram
    USER ||--o{ ACCESS_ASSIGNMENT : receives
    ROLE ||--o{ ACCESS_ASSIGNMENT : grants_at_scope
    ROLE ||--o{ ROLE_PERMISSION : contains
    PERMISSION ||--o{ ROLE_PERMISSION : maps

    WORKSPACE ||--o{ CUSTOMER : contains
    CUSTOMER ||--o{ SITE : contains
    CUSTOMER ||--o{ ACCESS_ASSIGNMENT : scopes
    SITE ||--o{ ACCESS_ASSIGNMENT : scopes

    CUSTOMER ||--o{ ASSET : owns
    SITE ||--o{ ASSET : contains
    ASSET_TYPE ||--o{ ASSET : classifies
    ASSET ||--o{ ASSET_RELATIONSHIP : source
    ASSET ||--o{ ASSET_RELATIONSHIP : target
    RELATIONSHIP_TYPE ||--o{ ASSET_RELATIONSHIP : classifies

    ASSET_TYPE ||--o{ CUSTOM_FIELD_ASSET_TYPE : applicability
    CUSTOM_FIELD_DEFINITION ||--o{ CUSTOM_FIELD_ASSET_TYPE : applies_to
    CUSTOM_FIELD_DEFINITION ||--o{ CUSTOM_FIELD_OPTION : offers
    CUSTOM_FIELD_DEFINITION ||--o{ ASSET_CUSTOM_FIELD_VALUE : defines
    CUSTOM_FIELD_OPTION o|--o{ ASSET_CUSTOM_FIELD_VALUE : selected_by
    ASSET ||--o{ ASSET_CUSTOM_FIELD_VALUE : enriched_by

    CUSTOMER ||--o{ INTEGRATION : owns
    SITE ||--o{ INTEGRATION : locates
    INTEGRATION ||--o{ DISCOVERY_RUN : executes
    ASSET ||--o{ ASSET_INTERFACE : exposes
    NETWORK o|--o{ ASSET_INTERFACE : connects
    ASSET ||--o{ ASSET_FACT : describes
    ASSET ||--o{ DOCUMENT : documents
    DISCOVERY_RUN o|--o{ DOCUMENT : generates

    USER o|--o{ AUDIT_EVENT : acts
    USER o|--o{ SYSTEM_SETTING : updates
    WORKSPACE o|--o{ AUDIT_EVENT : contextualizes
    CUSTOMER o|--o{ AUDIT_EVENT : contextualizes
    SITE o|--o{ AUDIT_EVENT : contextualizes

    USER {
        uuid id PK
        string email UK
        string password_hash
        string display_name
        boolean is_active
        boolean force_password_change
        integer session_version
        datetime last_login_at
        integer failed_login_count
        datetime locked_until
        string auth_provider
        string external_subject
        boolean mfa_enabled
        string accent_colour "nullable #RRGGBB preference"
    }
    ROLE {
        uuid id PK
        string name UK
        string description
        boolean system_defined
        boolean active
        integer sort_order
    }
    PERMISSION {
        uuid id PK
        string key UK
        string name
        string description
        string category
        boolean system_defined
    }
    ROLE_PERMISSION {
        uuid role_id PK,FK
        uuid permission_id PK,FK
    }
    ACCESS_ASSIGNMENT {
        uuid id PK
        uuid user_id FK
        uuid role_id FK
        string scope_type
        uuid customer_id FK
        uuid site_id FK
    }
    WORKSPACE {
        uuid id PK
        string name
        string slug UK
    }
    CUSTOMER {
        uuid id PK
        uuid workspace_id FK
        string name
        string status
    }
    SITE {
        uuid id PK
        uuid customer_id FK
        string name
        string status
    }
    ASSET_TYPE {
        uuid id PK
        string key UK
        string name UK
        string category
        string default_icon_url
        boolean system_defined
        boolean active
        integer sort_order
    }
    RELATIONSHIP_TYPE {
        uuid id PK
        string key UK
        string name UK
        string source_label
        string target_label
        string inverse_label
        boolean directional
        json allowed_source_asset_type_keys
        json allowed_target_asset_type_keys
        boolean system_defined
        boolean active
        integer sort_order
    }
    ASSET {
        uuid id PK
        uuid workspace_id FK
        uuid customer_id FK
        uuid site_id FK
        string asset_type FK
        string icon_url
        string name
        string source
        string external_id
    }
    ASSET_RELATIONSHIP {
        uuid id PK
        uuid source_asset_id FK
        uuid target_asset_id FK
        uuid customer_id FK
        uuid site_id FK
        string relationship_type FK
        boolean legacy_cross_context
        string notes
    }
    CUSTOM_FIELD_DEFINITION {
        uuid id PK
        string key UK
        string name
        string help_text
        string data_type
        boolean required
        boolean active
        boolean applies_to_all_asset_types
        integer sort_order
    }
    CUSTOM_FIELD_ASSET_TYPE {
        uuid field_definition_id PK,FK
        string asset_type_key PK,FK
    }
    CUSTOM_FIELD_OPTION {
        uuid id PK
        uuid field_definition_id FK
        string value
        string label
        boolean active
        integer sort_order
    }
    ASSET_CUSTOM_FIELD_VALUE {
        uuid id PK
        uuid asset_id FK
        uuid field_definition_id FK
        text value_text
        decimal value_number
        date value_date
        boolean value_bool
        uuid value_option_id FK
    }
    AUDIT_EVENT {
        uuid id PK
        uuid workspace_id FK
        uuid user_id FK
        string actor_email
        string actor_display_name
        string event_type
        string target_type
        uuid target_id
        uuid customer_id FK
        uuid site_id FK
        boolean success
        string summary
        string source_ip
        string request_id
        json metadata
        datetime created_at
    }
    SYSTEM_SETTING {
        uuid id PK
        string key UK
        json value
        string description
        boolean sensitive
        uuid updated_by_user_id FK
    }
```

`AccessAssignment` is both the role-assignment and access-scope-assignment
concept: one row links a user and role to one global, customer, or site scope.
Keeping permission membership in `RolePermission` and scope on the assignment
allows the same user to hold different roles in different contexts.

## Identity and access

### User

`User` is the database identity for local login. Email is the normalized unique
login identifier. `password_hash` is write-only outside the authentication
layer. Active/lock fields gate login, `force_password_change` gates normal API
use, and `session_version` invalidates already-issued signed sessions.

`auth_provider`, `external_subject`, and `mfa_enabled` are extension points; this
release implements local passwords, not external identity or MFA.
`accent_colour` is a nullable, per-user presentation preference stored as a
canonical uppercase `#RRGGBB` value. A null value selects the Atlas default
theme and preserves the existing appearance for upgraded accounts.

### Role, Permission, and AccessAssignment

Permissions have stable keys. Roles group them through `RolePermission`.
Protected built-in roles and system permissions are seeded idempotently.

The assignment scope constraint is:

| `scope_type` | `customer_id` | `site_id` | Meaning |
| --- | --- | --- | --- |
| `global` | null | null | Role permissions apply instance-wide. |
| `customer` | set | null | Apply to the customer and its sites. |
| `site` | set | set | Apply only to that site; the composite foreign key proves it belongs to the customer. |

Partial unique indexes prevent duplicate user/role assignments at each scope.
Deleting a user removes its assignments. Roles and scoped customer/site records
use restrictive references so assignments must be reviewed explicitly.

## Ownership and inventory

### Workspace, Customer, and Site

`Workspace` remains the instance-level container used by the existing model.
Customer names are unique within a workspace. Site names are unique within a
customer, and `(customer_id, site_id)` is a candidate key used by composite
ownership constraints.

Customer/site records use active/inactive status. A record with dependants is
not silently cascade-deleted.

### Asset and AssetRelationship

Every asset has a non-null customer and site, with a composite foreign key that
proves the site belongs to its customer. `asset_type` references the stable
`AssetType.key`; the nullable `icon_url` is the asset override.

A new relationship stores its customer/site context and stable relationship
type key. Both source and target must be distinct, accessible assets. New edges
must have endpoints in the same customer/site. A retained legacy cross-context
edge has `legacy_cross_context=true` and is treated as historical compatibility
data: authorization requires both endpoints, and mutation cannot create another
cross-context edge. Its stored relationship context is copied from the source
asset during migration; endpoint authorization remains authoritative for reads.

Interfaces, facts, and documents depend on their asset. Every integration
belongs to exactly one customer and one site, with a composite foreign key that
proves the site belongs to that customer; discovery runs belong to an
integration. Core sync derives ownership from the validated integration/run
context rather than accepting plugin-selected tenancy.

## Managed reference data

### AssetType

The UUID `id` is the internal primary key; the unique string `key` is the stable
inventory reference used by assets. Display name, description, category,
default icon URL, active state, and sort order are editable subject to policy. A
system-defined or referenced type cannot be deleted; inactive types remain
resolvable for existing assets.

### RelationshipType

Relationship types similarly have an internal UUID and a stable unique key.
Labels, inverse label,
directionality, and optional allowed source/target asset-type key lists drive
validation and display. Used/system types follow the same delete-versus-
deactivate lifecycle.

## Custom fields

`CustomFieldDefinition` holds the stable key, type, requirement, order, and
global-applicability flag. `CustomFieldAssetType` is the many-to-many
applicability table for selected asset types. The service counts global plus
specific active definitions and rejects a configuration above 10 for any asset
type.

Dropdown definitions own ordered `CustomFieldOption` rows. Used options are
deactivated rather than removed. `AssetCustomFieldValue` has one row per
asset/definition and exactly one populated typed column. Text, multiline text,
and URL use `value_text`; numbers, dates, booleans, and dropdown selections use
their dedicated column. A composite option foreign key ensures the selected
option belongs to the same definition.

## AuditEvent

Audit events are append-only through normal application APIs. Nullable actor
identity supports failed login attempts; email/display snapshots retain useful
history after identity changes. Customer/site are nullable for global actions.
The safe summary and metadata must exclude passwords, hashes, bootstrap values,
cookies, signed sessions, and other secrets.

## SystemSetting

System settings use a stable unique key and JSON value. Values marked sensitive
are redacted by the response model; updates require the global protected
permission and record the actor in both `updated_by_user_id` and the audit log.
The schema does not make an environment secret safe to expose as a setting, so
session/database/bootstrap secrets remain outside this table.

## Migration invariants

The foundation migration preserves existing data and seeds stable definitions:

- A per-customer `Default Site` backfills assets and integrations that
  previously had no valid site under their customer. Asset and integration
  sites are non-null after the migration.
- A network may intentionally be customer-wide (`site_id = NULL`), while every
  site-specific network has a composite customer/site foreign key. Invalid
  legacy site references normalize to customer-wide rather than being deleted.
- Legacy string type values become managed type keys without changing asset or
  relationship meaning. Blank asset and relationship type values normalize to
  `unknown` and `related_to`, respectively.
- Existing users receive a global Master Administrator assignment so an upgrade
  cannot lock them out; operators then reduce access deliberately.
- Existing cross-context relationships are retained as legacy history, while
  all newly created/updated relationships enforce same-customer/same-site
  endpoints and read access to both endpoints.
- Seed/backfill operations are idempotent and never depend on dropping the
  database.
