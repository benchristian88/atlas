# Service dependencies and capability graph

## Typed dependency records

Service dependencies reuse Atlas Relationship Types while making endpoint applicability
explicit. A Relationship Type may be enabled for an endpoint pair such as
`service → asset` or `service → service`. The API rejects inactive types and
types that are not enabled for the requested pair. Existing Asset relationship
behavior is unchanged.

Three temporal link tables provide the dependency model:

- **Service → Asset** says which technical Assets implement or support a
  Service, for example `Authentik runs on authentik-lxc`.
- **Service → Service** says which operational capabilities depend on other
  capabilities, for example `Authentik depends on DNS`.
- **Service → Business Function** says which lightweight capability a Service
  supports, for example `Authentik supports Identity and Access`.

Each link has a creation time and an optional `valid_to`. Removing a link ends
it instead of deleting it. The UI asks for confirmation, the assertion is
retracted, and a meaningful removal event is recorded. History can be requested
with `include_history=true`.

Service self-dependency is invalid. Legitimate cycles between different
Services are allowed because real systems can be mutually dependent. Exact
duplicate active edges are rejected by database constraints. Targets must be
within the permitted customer/site scope; Business Functions and customer-wide
Services can be shared into a compatible site context.

## Ownership and transfers

The source Service owns the relationship. A current row has the source's
customer and site. A null site represents customer-wide ownership. Both
endpoints belong to the same customer.

| Source Service | Asset target | Service or Business Function target |
| --- | --- | --- |
| Site-specific | Same site | Same site or customer-wide |
| Customer-wide | Any site in the same customer | Customer-wide or any site in the same customer |

The existing relationship management permission must cover both endpoints.
The caller also needs the target's entity view permission before a mutation can
return its details or record its name. Reads check the recorded relationship
scope and both endpoints. Site grants do not cover customer-wide records.
Group writes authorize all affected members, including members being removed.

Asset transfers retain active dependencies when the destination remains
compatible with every owning Service. Dependencies of archived Services count
until explicitly ended. Asset Relationships and Interfaces still restrict
Asset moves. Service site moves require ending outgoing links and groups,
which retain the Service's original recorded scope. Incoming links to Services
and Business Functions can remain active when their source scope is compatible
with the proposed target site. A blocked move returns a generic HTTP 409.

Rows with `valid_to` set retain their original IDs and ownership. They do not
block transfers. Relationship history returns an ended row when the reader
can view its recorded scope and both live endpoints within the original
customer. Knowledge Changes retain their recorded scope and historical
snapshots. Assertions and audit events are retained. Typed Service assertion
reads check live endpoint visibility, and current claims also require
compatible ownership.

## Transaction ordering and legacy records

Relationship and group writes lock their endpoints with PostgreSQL
`FOR UPDATE` in canonical subject order. Assets come first, followed by
Services and Business Functions. Rows within each type lock in ascending UUID
order. The request then refreshes scopes and grants before mutating
relationship, group, membership, or assertion rows.
Asset Relationship and Interface creation lock their Assets before writing
references, so their foreign-key locks cannot precede the Asset writer lock.

Transfers lock the moving record before querying active edges. The competing
relationship writer must hold that same endpoint lock. Transfer guards read
the other endpoints without acquiring additional locks. An owning Service with
an active outgoing edge cannot change its recorded scope, which makes those
reads sufficient. The S1.1 completeness and gap writers use
`FOR NO KEY UPDATE` on the same entity rows. Dependency creation and ending
reevaluate the affected Services in the same transaction. Manual assertions
reuse the held canonical lock. Their source references take foreign-key
`KEY SHARE`, which is compatible with the source writer mode used by
reconciliation under ADR 0017.

The database enforces endpoint existence, valid customer/site pairs, active
uniqueness, and membership cardinality. The cross-row ownership checks are
enforced by the application. Legacy mismatches can still exist in stored data.
Current relationship lists, counts, graph, analysis and completeness rules
exclude them. Normal relationship and group edits fail closed with HTTP 404
when an endpoint is unavailable or incompatible. Previously stored
completeness results reflect their last evaluation and need reevaluation
to reflect the corrected rules. An explicit owner-reviewed remediation is
required for invalid edges that cannot be made compatible by a normal transfer.

## Direction and labels

The stored source and target retain semantic direction. A Service detail page
shows outgoing edges as dependencies and incoming Service edges as "Required
by". Relationship source labels are returned by the API so the UI does not
guess meaning from a key.

Incoming/reverse traversal does not reverse the stored relationship or create a
new semantic edge. The canonical edge remains source to target; an inverse label
is presentation metadata only. The operational graph preserves this distinction in its shared
edge contract.

Adding or changing a dependency creates a declared accepted relationship
assertion. Removing it retracts that assertion without deleting provenance.
Dependency actions also create Knowledge Changes and trigger Service
completeness reevaluation.

## Business Functions

A Business Function is a deliberately small customer/site-scoped capability
record with a name, description, owner label, optional criticality, and active
state. Several Services can support one Function and one Service can support
several Functions. This is not a process hierarchy, portfolio, organization,
or enterprise capability taxonomy.

## Graph projection

`GET /api/services/{id}/graph` returns a focused node/edge projection containing
the selected Service, connected Services, supporting Assets, and Business
Functions. `GET /api/business-functions/{id}/graph` projects a Function through
its supporting Services to their Assets, making connected infrastructure visible.
Nodes include entity type, display labels, and navigable UI paths; edges retain
relationship labels and direction.

These endpoints now use the shared operational graph builder while
retaining their public response shapes. The builder applies endpoint-by-endpoint
authorization and current-valid filtering. The focused routes remain structural
projections: they do not perform outage simulation or full Impact Analysis.

## Lean dependency semantics

Dependency semantics preserve `required_for_operation` while adding the minimum homelab
semantics needed by later analysis. A temporal `DependencyGroup` describes one
operational need for a subject Service:

- `requirement` is `required` or `optional`;
- `strategy` is `all` or `any`; and
- `failure_effect` is `unavailable`, `degraded`, or explicitly `unknown`.

Temporal `DependencyGroupMembership` rows associate any mixture of the
Service's current Service→Asset and outgoing Service→Service dependency records
with that group. The underlying dependencies remain the authoritative
relationships; groups add meaning across them and do not merge the two tables.

Ungrouped dependencies remain valid. Their required/optional meaning is derived
unchanged from `required_for_operation`, their strategy is absent because they
are not a multi-member set, and their failure effect is `unknown`. Migration
does not create groups or infer outage consequences for existing rows.

Group changes create a superseding group version and end the previous group and
memberships. This keeps earlier semantics truthful without event sourcing or
rewriting dependency history. Ending a dependency also ends its current group
membership; ending a group leaves its dependency relationships intact.

The normal Service detail workflow exposes these semantics using “Required”,
“Optional”, “All required”, “Any one is sufficient”, “Service unavailable”,
“Service degraded”, and “Unknown”. The existing
`service_dependencies.view`/`service_dependencies.manage` permissions and
customer/site checks apply to group reads and mutations.

Dependency impact analysis applies these stored semantics through bounded, deterministic,
cycle-safe, authorization-safe analysis and explains results with actual
dependency paths. See [dependency analysis](dependency-analysis.md) for `all`/`any`
evaluation, degraded/unknown propagation, conservative aggregation, and the
read-only scenario API. Structural Asset relationships and Business Function
support links do not acquire failure semantics.

The model remains additively extensible to `minimum`, quorum,
`minimum_available`, weighted, conditional, and richer group rules, but those
are later enterprise capabilities rather than homelab beta requirements.
