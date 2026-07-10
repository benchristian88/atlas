# Atlas Data Model v0

## Core Entities

### User

Represents a person who can log into Atlas.

Fields:

- id
- email
- password_hash
- display_name
- created_at
- updated_at

### Workspace

Represents the top-level Atlas environment.

Fields:

- id
- name
- slug
- created_at
- updated_at

### Customer

Represents a client or internal organisation.

Fields:

- id
- workspace_id
- name
- description
- created_at
- updated_at

### Site

Represents a physical or logical location.

Fields:

- id
- customer_id
- name
- address
- notes
- created_at
- updated_at

### Integration

Represents a configured discovery source.

Fields:

- id
- customer_id
- site_id
- plugin_id
- name
- base_url
- username_or_token_id
- secret_reference
- verify_tls
- status
- created_at
- updated_at

### Discovery Run

Represents one execution of a discovery job.

Fields:

- id
- integration_id
- status
- started_at
- completed_at
- error_message
- raw_payload
- summary

### Asset

Represents a discovered or manually created infrastructure object.

Fields:

- id
- workspace_id
- customer_id
- site_id
- source_integration_id
- external_id
- name
- asset_type
- vendor
- status
- description
- metadata
- first_seen_at
- last_seen_at
- created_at
- updated_at

### Asset Relationship

Represents a relationship between two assets.

Fields:

- id
- source_asset_id
- target_asset_id
- relationship_type
- metadata
- created_at
- updated_at

Relationship examples:

- runs_on
- uses_storage
- connected_to
- depends_on
- backs_up_to
- protects

### Asset Fact

Represents flexible facts about an asset.

Fields:

- id
- asset_id
- key
- value
- source
- created_at
- updated_at

### Document

Represents generated or manually edited documentation.

Fields:

- id
- asset_id
- title
- content_markdown
- generated_from_discovery_run_id
- created_at
- updated_at

### Audit Event

Represents a security or system event.

Fields:

- id
- workspace_id
- user_id
- event_type
- target_type
- target_id
- metadata
- created_at