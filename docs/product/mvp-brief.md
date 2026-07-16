# Atlas MVP brief

## Purpose

Atlas is an infrastructure knowledge, documentation, and topology platform for
homelabs, internal IT teams, and MSPs. It should remain simple for one
customer/site while establishing the isolation needed for many customers and
sites.

## MVP outcome

The MVP combines two foundations:

1. A secure, customer/site-scoped core where administrators can manage users,
   inventory context, reference data, enrichment, and audit history.
2. A vendor-neutral discovery loop that can validate a Proxmox connection,
   discover infrastructure, normalize it idempotently, and generate useful
   asset documentation/topology.

The security foundation precedes broader discovery: a plugin or background job
must not ingest data until its customer/site ownership and permission boundary
are explicit.

## Core user journeys

### First installation and identity

1. An operator deploys Atlas and supplies one-time bootstrap credentials only
   for an empty users table.
2. Atlas creates one database-backed global Master Administrator with a hashed
   password and forced-password-change state.
3. The operator signs in, changes the password, removes bootstrap values, and
   manages future users through Atlas.
4. Profile, logout, password change, lock/disable state, and session-version
   invalidation work without exposing a browser-storage token.

### Homelab context

1. A user has access to one customer/site such as `Home / Homelab`.
2. Atlas selects it automatically and keeps it visible in the header.
3. Inventory, topology, counts, and creation use that context without forcing
   the user through MSP-oriented choices.

### MSP context and access

1. A user may have role assignments at global, customer, or selected-site scope.
2. The header selector contains only authorized customers/sites.
3. The API filters every object, list, search, total, and topology response by
   explicit permission and assignment scope.
4. Customer Administrators cannot access another customer; Viewers cannot
   mutate data; manually substituted IDs do not expand access.

### Administration and enrichment

1. Authorized administrators manage users, roles/permissions, assignments,
   customers, sites, asset types, relationship types, and custom fields.
2. System-defined or referenced types cannot be deleted; inactive types remain
   readable on historical records.
3. Global and asset-type-specific typed fields enrich an asset, with no more
   than 10 active applicable fields for any asset type.
4. Asset/type HTTPS icon URLs resolve through asset override, type default, and
   generic fallback without server-side remote fetching.
5. Security-sensitive and administrative actions create safe read-only audit
   events.

### Discovery and documentation

1. An authorized user configures a Proxmox integration for a concrete
   customer/site with read-only API-token credentials.
2. Atlas validates the connection and a worker executes discovery outside the
   web-request lifecycle.
3. Proxmox nodes, QEMU VMs, LXCs, storage pools, and network bridges normalize to
   stable vendor-neutral identities.
4. Repeated sync updates the same assets and `last_seen_at` instead of creating
   duplicates; absent assets become stale rather than being deleted.
5. Atlas retains raw discovery results for debugging and generates readable
   Markdown documentation without copying secrets/raw payloads into pages.

## Built-in access model

- **Master Administrator**: every permission globally, including users, roles,
  protected configuration, and audit.
- **Administrator**: broad operational/administrative access within assigned
  scope, without implicit Master-only platform control.
- **Customer Administrator**: manages permitted resources only inside assigned
  customers/sites.
- **Viewer**: read-only access inside assigned scope.

Roles map to explicit permission keys. Role assignments independently bind a
role to global, customer, or site scope, allowing one user to hold different
roles in different contexts. Backend policy is authoritative; permission-aware
navigation is a usability layer.

## Managed data rules

- Every asset belongs to a customer and site.
- New relationships require distinct, authorized source/target assets in the
  same customer and site. Migrated legacy cross-context edges are retained but
  require access to both endpoints and cannot be recreated.
- Asset/relationship types have stable global keys in the MVP. Used or
  system-defined records are deactivated, not destructively deleted.
- Custom fields are structured typed definitions/value rows, not hard-coded
  nullable asset columns or arbitrary unvalidated JSON.
- Icons are HTTPS URL metadata; remote SVG is rejected and broken images fall
  back to a generic icon.
- Audit records are not editable through normal application APIs.

## Non-goals for this MVP

- Billing or commercial multi-MSP tenancy above the Atlas instance/workspace.
- SSO/OIDC/SAML, MFA flows, recovery codes, or email-based forgotten-password
  recovery.
- Arbitrarily granular per-record policies, delegated role administration, or
  plugin-defined permission installation.
- Customer-specific managed asset/relationship types or custom-field
  definitions.
- New cross-site/cross-customer relationships.
- Uploaded icon/media storage or server-side icon proxying.
- Tamper-evident external audit storage.
- AI-generated remediation.
- A full production scheduler/queue control plane or discovery plugins beyond
  the initial Proxmox implementation.

## MVP success criteria

The MVP is successful when:

- Docker Compose can migrate a fresh or existing database without destroying
  current assets/relationships.
- One-time bootstrap creates only the first Master Administrator; permanent
  credentials do not come from `.env`.
- Cookie login, forced password change, profile, logout, password/session
  invalidation, disable/lock behavior, and secret hygiene are verified.
- Administrators can create users and assign explicit roles/scopes without
  allowing removal of the final usable global Master Administrator.
- Customer/site isolation covers lists, objects, search, counts, topology, and
  request-ID substitution.
- A single-site user receives automatic streamlined context while an authorized
  multi-customer user can switch context in the header.
- Managed type lifecycle, the 10-field rule, typed validation, icon resolution,
  and read-only safe audit records pass backend tests.
- Existing assets and integrations with missing or mismatched sites receive a
  per-customer default site, integration sites become required, legacy users
  retain upgrade access, and existing type keys/history remain resolvable.
  Blank asset/relationship types resolve as `unknown`/`related_to`.
- Proxmox discovery is idempotent, retains raw results safely, and produces
  vendor-neutral assets and generated documentation.
- Supported API tests and the web production build pass, and operator/security/
  migration limitations are documented without overstating validation.

## Recommended next increment

Deepen topology-context visualization after the scoped foundation, then connect
plugin discovery/ingestion permissions to complete worker orchestration. Follow
with SSO/MFA and external audit export before production hardening.
