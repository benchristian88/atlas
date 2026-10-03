# Service dependencies and capability graph

## Typed dependency records

Release C1 reuses Atlas Relationship Types while making endpoint applicability
explicit. A Relationship Type may be enabled for an endpoint pair such as
`service → asset` or `service → service`. The API rejects inactive types and
types that are not enabled for the requested pair. Existing Asset relationship
behavior is unchanged.

Three temporal link tables provide the C1 model:

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

## Direction and labels

The stored source and target retain semantic direction. A Service detail page
shows outgoing edges as dependencies and incoming Service edges as "Required
by". Relationship source labels are returned by the API so the UI does not
guess meaning from a key.

Incoming/reverse traversal does not reverse the stored relationship or create a
new semantic edge. The canonical edge remains source to target; an inverse label
is presentation metadata only. C2.1 preserves this distinction in its shared
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

These endpoints now use the C2.1 shared operational graph builder while
retaining their public response shapes. The builder applies endpoint-by-endpoint
authorization and current-valid filtering. The focused routes remain structural
projections: they do not perform outage simulation or full Impact Analysis.

## Lean dependency semantics

C2.2 preserves `required_for_operation` while adding the minimum homelab
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

C2.3 applies these stored semantics through bounded, deterministic,
cycle-safe, authorization-safe analysis and explains results with actual
dependency paths. See [dependency analysis](dependency-analysis.md) for `all`/`any`
evaluation, degraded/unknown propagation, conservative aggregation, and the
read-only scenario API. Structural Asset relationships and Business Function
support links do not acquire failure semantics.

The model remains additively extensible to `minimum`, quorum,
`minimum_available`, weighted, conditional, and richer group rules, but those
are later enterprise capabilities rather than Homelab Ready requirements.
