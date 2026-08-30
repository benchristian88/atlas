# Atlas MVP brief

## Document status

The foundation described by this brief is implemented through Release C1, with
the limitations recorded in [`feature-ledger.md`](feature-ledger.md). The live
Integration/worker path remains partial even though discovery simulation,
reconciliation, plugin contracts, and core sync components exist.

This document is retained as the historical product baseline. Future planning is
maintained in [`development-roadmap.md`](development-roadmap.md), and the next
implementation increment is described in
[`release-c2-plan.md`](release-c2-plan.md).

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

Release C1 adds a third operational foundation: first-class Services and
Business Functions linked to the technical Assets and Services that provide
them.

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
3. Global and asset-type-specific typed fields enrich an Asset, with no more
   than 10 active applicable fields for any Asset Type.
4. Asset/type HTTPS icon URLs resolve through Asset override, type default, and
   generic fallback without server-side remote fetching.
5. Security-sensitive and administrative actions create safe read-only audit
   events.

### Discovery and documentation

The intended end-to-end journey is:

1. An authorized user configures a Proxmox Integration for a concrete
   customer/site with read-only API-token credentials.
2. Atlas validates the connection and a worker executes discovery outside the
   web-request lifecycle.
3. Proxmox nodes, QEMU VMs, LXCs, storage pools, and network bridges normalize to
   stable vendor-neutral identities.
4. Repeated sync updates the same Assets and `last_seen_at` instead of creating
   duplicates; absent Assets become stale rather than being deleted.
5. Atlas retains raw discovery results for debugging and generates readable
   Markdown documentation without copying secrets/raw payloads into pages.

At the current implementation baseline, simulation, evidence, reconciliation,
plugin adapters, sync components, and generated-document storage exist, but the
configured Integration-to-worker journey is not yet complete.

### Knowledge and reconciliation

1. Discovery evidence remains distinct from accepted operational knowledge.
2. Source-current assertions show what a source most recently claimed.
3. Reconciliation controls whether conflicting discovered knowledge updates the
   operational model.
4. Meaningful Knowledge Changes describe user-relevant history separately from
   security Audit Events.
5. Configurable completeness requirements create knowledge gaps without
   deleting or silently changing operational records.

### Homelab Services and capabilities

1. A user records an operational Service separately from the technical Assets
   that implement it.
2. The Service links to supporting Assets, upstream/downstream Services, and a
   lightweight Business Function with typed, directional relationships.
3. Owner/contact labels, criticality, RTO/RPO, recovery notes, runbook, and
   documentation establish useful homelab operations knowledge without an
   enterprise CMDB workflow.
4. Manual fields and links retain assertions and meaningful change history;
   configuration-driven requirements surface missing Service knowledge.
5. Focused graph projections answer which infrastructure supports a Service and
   which Assets are affected through a Business Function.

## Built-in access model

- **Master Administrator:** every permission globally, including users, roles,
  protected configuration, and audit.
- **Administrator:** broad operational/administrative access within assigned
  scope, without implicit Master-only platform control.
- **Customer Administrator:** manages permitted resources only inside assigned
  customers/sites.
- **Viewer:** read-only access inside assigned scope.

Roles map to explicit permission keys. Role assignments independently bind a
role to global, customer, or site scope, allowing one user to hold different
roles in different contexts. Backend policy is authoritative; permission-aware
navigation is a usability layer.

## Managed data rules

- Every Asset belongs to a customer and site.
- Services and Business Functions belong to a customer and may be customer-wide
  or site-scoped according to their model rules.
- New Asset relationships require distinct, authorized source/target Assets in
  the same customer and site. Migrated legacy cross-context edges are retained
  but require access to both endpoints and cannot be recreated.
- Asset/Relationship Types have stable global keys in the MVP. Used or
  system-defined records are deactivated, not destructively deleted.
- Custom fields are structured typed definitions/value rows, not hard-coded
  nullable Asset columns or arbitrary unvalidated JSON.
- Icons are HTTPS URL metadata; remote SVG is rejected and broken images fall
  back to a generic icon.
- Audit records are not editable through normal application APIs.
- Evidence, assertions, reconciliation, accepted records, changes, and gaps keep
  their distinct meanings.
- Ending a temporal Service link preserves its history rather than deleting it.

## Non-goals for this MVP and C1

- Billing or commercial multi-MSP tenancy above the Atlas instance/workspace.
- SSO/OIDC/SAML, MFA flows, recovery codes, or email-based forgotten-password
  recovery.
- Arbitrarily granular per-record policies, delegated role administration, or
  plugin-defined permission installation.
- Customer-specific managed Asset/Relationship Types or custom-field
  definitions.
- New cross-site/cross-customer relationships.
- Uploaded icon/media storage or server-side icon proxying.
- Tamper-evident external audit storage.
- AI-generated remediation.
- A full production scheduler/queue control plane or discovery plugins beyond
  the initial Proxmox implementation.
- People/Team ownership, formal Knowledge Objects, full backup/recovery,
  recursive impact analysis, intended-state simulation, ITSM workflows, or a
  Service catalog.

## MVP and C1 success criteria

The baseline is successful when:

- Docker Compose can migrate a fresh or existing database without destroying
  current Assets, relationships, knowledge, or Services.
- One-time bootstrap creates only the first Master Administrator; permanent
  credentials do not come from `.env`.
- Cookie login, forced password change, profile, logout, password/session
  invalidation, disable/lock behavior, and secret hygiene are verified.
- Administrators can create users and assign explicit roles/scopes without
  allowing removal of the final usable global Master Administrator.
- Customer/site isolation covers lists, objects, search, counts, topology,
  focused graphs, and request-ID substitution.
- A single-site user receives automatic streamlined context while an authorized
  multi-customer user can switch context in the header.
- Managed type lifecycle, the 10-field rule, typed validation, icon resolution,
  and read-only safe audit records pass backend tests.
- Existing data receives safe additive migration/backfill behavior and legacy
  users retain upgrade access.
- Discovery simulation and reconciliation preserve source evidence and accepted
  operational knowledge separately.
- Proxmox discovery components are idempotent, retain raw results safely, and
  produce vendor-neutral Assets and generated documentation.
- First-class Services, dependencies, Business Functions, recovery fields,
  provenance, completeness, and focused graph views work without converting
  legacy Service-type Assets automatically.
- Supported API tests, web tests/build, plugin tests, and migration checks pass
  where claimed, and limitations are documented without overstating live
  validation.

## Next roadmap increment

The next planned increment is **Release C2.1 — Shared Operational Graph**.

This is a sequencing decision. B2 — Operational Integrations and live discovery
remains a parallel incomplete workstream and is not included in C2.1.

C2.1 will:

- derive a reusable typed graph from accepted relational records;
- preserve API-owned authorization and semantic direction;
- refactor current focused graph endpoints through compatibility adapters;
- establish stable graph identity and bounded projection; and
- avoid outage, recovery, or change-safety conclusions until later semantics and
  evidence exist.

See:

- [`development-roadmap.md`](development-roadmap.md)
- [`release-c2-plan.md`](release-c2-plan.md)
- [`../architecture/operational-graph.md`](../architecture/operational-graph.md)
- [`../decisions/0001-shared-operational-graph.md`](../decisions/0001-shared-operational-graph.md)
