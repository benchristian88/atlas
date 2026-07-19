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
its supporting Services to their Assets, making affected infrastructure visible.
Nodes include entity type, display labels, and navigable UI paths; edges retain
relationship labels and direction.

These endpoints reuse the existing graph concepts and authorization boundary.
They intentionally avoid global recursive traversal, path scoring, outage
simulation, and full impact analysis. Their typed output is the foundation a
later impact-analysis release can traverse more deeply.
