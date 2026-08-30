# Operational graph architecture

Status: planned for Release C2.1

This document describes a future architecture. It is not an implementation
claim until the feature ledger is re-audited after delivery.

## Purpose

Atlas currently has several graph-shaped product surfaces:

- the Knowledge Graph topology lenses over Assets and Asset relationships;
- a focused Service graph;
- a focused Business Function graph; and
- summary and completeness views that depend on related operational records.

The next product surfaces — Homepage environment intelligence, Service
Operations, Impact Analysis, and Change Simulation — need consistent graph
identity, direction, scope, metadata, and traversal behavior.

Release C2.1 introduces a **shared operational graph projection** in the API. It
turns accepted relational records into a typed, bounded graph response without
creating a second source of truth.

## Architectural context

The completed foundation through C1 established these invariants:

- PostgreSQL is the durable system of record.
- The FastAPI API owns authentication, permissions, scope, validation, and
  persistence.
- Every interactive result is constrained by global/customer/site assignments.
- Evidence is not accepted operational knowledge.
- Assertions retain provenance and lifecycle independently from the operational
  record.
- Reconciliation is required before conflicting discovery changes accepted
  operational knowledge.
- Knowledge gaps describe missing or insufficient knowledge and are not
  reconciliation items.
- Services are separate from the Assets that implement them.
- Service dependency records are temporal and preserve source/target direction.
- Legitimate cycles between Services are allowed.
- Current focused graph routes intentionally avoid global recursive impact
  analysis.

C2.1 must build on these decisions rather than bypassing them.

## Decision summary

The governing decision is
[`../decisions/0001-shared-operational-graph.md`](../decisions/0001-shared-operational-graph.md).

In summary:

1. PostgreSQL operational records remain canonical.
2. The operational graph is derived at read time in the API.
3. Accepted current knowledge is the default graph input.
4. The graph exposes provenance and completeness qualifiers where available but
   does not invent a global confidence score in C2.1.
5. Existing focused graph endpoints remain compatible while their internal
   assembly is replaced.
6. No graph database, materialized graph store, scenario mutation, or impact
   propagation is introduced in C2.1.

## Terminology

### Accepted operational knowledge

The records Atlas currently uses to describe the working environment, including
Assets, Asset relationships, Services, Service dependencies, and Business
Functions after any required reconciliation.

A source-current assertion is not automatically accepted operational knowledge.

### Operational graph projection

A request-time typed representation of accepted operational records as nodes and
edges. It is a read model, not a persistence model.

### Focus

The authorized Asset, Service, or Business Function from which a bounded graph
projection begins.

### Structural traversal

Graph expansion used to collect connected nodes and edges. Structural traversal
does not itself decide failure propagation or business impact.

### Analysis traversal

A later C2.3 operation that applies dependency semantics, hypothetical states,
reason codes, and confidence qualification to structural graph paths.

## Current source model

```mermaid
flowchart LR
    A1[Asset] -->|AssetRelationship| A2[Asset]
    S1[Service] -->|ServiceAssetDependency| A3[Asset]
    S1 -->|ServiceDependency| S2[Service]
    S1 -->|ServiceBusinessFunction| BF[Business Function]
```

| Source record | Semantic role | Current temporal behavior |
| --- | --- | --- |
| `Asset` | Technical node | Current operational record |
| `AssetRelationship` | Asset-to-Asset structural or dependency edge | Current record; does not yet share the C1 temporal link contract |
| `Service` | Operational capability node | Current or archived record |
| `ServiceAssetDependency` | Service-to-Asset edge | `valid_from` and optional `valid_to` |
| `ServiceDependency` | Service-to-Service edge | `valid_from` and optional `valid_to`; non-self cycles allowed |
| `BusinessFunction` | Lightweight business capability node | Current active/inactive record |
| `ServiceBusinessFunction` | Service-to-Business Function edge | `valid_from` and optional `valid_to` |
| `RelationshipType` | Stable key, labels, direction, endpoint applicability | Managed reference data |
| `KnowledgeCompletenessSummary` | Current completeness qualifier | One current summary per supported entity |
| `KnowledgeGap` | Missing, stale, or insufficient knowledge | Lifecycle-preserving active and historical gaps |
| `KnowledgeAssertion` | Provenance and claim history | Source-current and accepted states remain separate |

The graph builder reads the operational records. It may attach assertion,
source, completeness, or gap summaries, but it must not substitute an
unaccepted assertion for an operational node or edge.

## Logical architecture

```mermaid
flowchart LR
    DB[(PostgreSQL operational records)]
    LOAD[Typed node and edge loaders]
    SCOPE[Authorization and scope filter]
    BUILD[OperationalGraphBuilder]
    API[Operational graph API]
    ADAPT[Compatibility adapters]
    VIEWS[Homepage / Service Operations / future analysis views]
    OLD[Existing Service and Business Function graph contracts]

    DB --> LOAD --> SCOPE --> BUILD --> API --> VIEWS
    BUILD --> ADAPT --> OLD
```

The API remains the only authority for the graph result. The web application may
layout, filter, and present the response but may not infer inaccessible nodes,
relationship semantics, impact, confidence, or severity.

## Graph identity

Node identity must include the entity type because UUID uniqueness is guaranteed
within a table, not across all graph entity tables.

```text
asset:<uuid>
service:<uuid>
business_function:<uuid>
```

Edge identity must include the edge family:

```text
asset_relationship:<uuid>
service_asset:<uuid>
service_service:<uuid>
service_business_function:<uuid>
```

The response should retain the underlying UUID separately for route links and
API use. Web graph libraries should use the namespaced key.

## Node contract

A C2.1 node should contain enough information for consistent display and later
analysis qualification without becoming an unbounded entity serializer.

Recommended fields:

- `key`;
- `entity_type`;
- `entity_id`;
- `customer_id`;
- `site_id`;
- `name`;
- `subtitle` or type label;
- `href`;
- lifecycle state where applicable;
- operational state where applicable;
- criticality key/name where applicable;
- completeness status;
- open knowledge-gap count;
- source where available; and
- updated time where available.

The graph response should not copy every custom field, note, assertion, or raw
evidence item. Detail routes remain the place for full records.

## Edge contract

A C2.1 edge should preserve semantic direction and its source record family.

Recommended fields:

- `key`;
- `edge_family`;
- `edge_id`;
- `source_key`;
- `target_key`;
- managed relationship type key and name;
- source-side display label;
- `required_for_operation` where the source model supports it;
- `valid_from` and `valid_to` where supported;
- source where available; and
- `knowledge_state`, initially `accepted` for the operational projection.

The graph may be visually laid out left-to-right, top-to-bottom, or around a
focus node, but the stored `source_key` and `target_key` must never be reversed
only to suit presentation.

## Relationship semantics

C2.1 carries current relationship metadata; it does not yet decide how a failure
propagates.

For example:

- `runs_on` may indicate a hosting relationship;
- `depends_on` may indicate an operational dependency;
- `uses_storage` may indicate a storage path;
- `supports` may connect a Service to a Business Function; and
- `connects_to` may be structural rather than a sufficient outage rule.

The web must render API-provided labels rather than maintain hard-coded semantic
key lists for operational conclusions.

Release C2.2 adds explicit dependency groups and failure effects. Until then,
`required_for_operation` is useful metadata but is not enough to model
redundancy or quorum.

## Authorization and non-disclosure

### Focus authorization

The API resolves the focus record and applies the corresponding permission and
scope check. An unauthorized focus should return the established non-disclosing
response behavior.

### Expansion authorization

Every edge expansion resolves both endpoints. The complete edge is omitted when
either endpoint cannot be viewed. The API must not return:

- a dangling edge;
- an inaccessible endpoint ID or label;
- a hidden-node count;
- a warning that reveals an inaccessible entity;
- a truncation count that includes inaccessible entities; or
- an error message that distinguishes an inaccessible endpoint from a missing
  endpoint where current policy hides existence.

### Mixed permissions

A principal may be allowed to view an Asset but not Services, or a Business
Function but not an adjacent Asset. The graph result includes only the subgraph
permitted by the caller's explicit permissions and assignments.

The active workspace context narrows the request but does not replace object
scope checks.

## Accepted knowledge and provenance

The default operational graph includes:

- accepted `Asset` and `Service` fields;
- current accepted Asset relationships;
- active temporal Service links at the requested time; and
- active Business Functions.

It excludes unaccepted source observations as operational edges.

Where bounded and useful, the graph can expose qualifiers such as:

- source (`manual`, discovered/accepted, or another current source label);
- completeness status;
- open gap count;
- last updated time;
- assertion or evidence summary references; and
- a warning that an entity has unresolved knowledge.

C2.1 does not calculate a universal numeric confidence score. Release C2.3 must
define a documented formula before such a number is shown.

## Temporal behavior

The projection uses a request analysis time called `as_of`.

For temporal Service links, an edge is active when:

```text
valid_from <= as_of
and (valid_to is null or valid_to > as_of)
```

The exact inclusive/exclusive boundary should be implemented consistently with
existing repository conventions and covered by tests.

For current source models without temporal history, such as current
`AssetRelationship`, C2.1 returns the current accepted record. It must not imply
that an arbitrary historical `as_of` query reconstructs Asset topology that was
never stored.

The response should include the actual `as_of` used and may include a warning
when part of the result is current-only.

## Projection boundaries

C2.1 supports a focused bounded projection:

- focus entity required;
- structural depth `0..2`;
- incoming, outgoing, or both directions;
- optional edge-family filter;
- deterministic node limit; and
- explicit truncation.

Depth is measured by graph edges from the focus. It is a display/projection
boundary, not a failure-propagation boundary.

## Builder behavior

The builder should:

1. resolve and authorize the focus;
2. create its namespaced node;
3. load eligible edges for the current frontier in deterministic batches;
4. resolve and authorize endpoints;
5. apply active and `as_of` rules;
6. add each authorized edge once;
7. add newly discovered nodes once;
8. queue unvisited nodes until the requested structural depth;
9. stop deterministically at the node limit;
10. attach bounded metadata in batches;
11. sort the final nodes and edges by stable keys; and
12. return warnings and truncation state.

A visited-node set prevents infinite expansion through cycles. It must not remove
an edge between nodes already present.

## Determinism

The same principal, database state, query, and `as_of` time should produce the
same ordered response.

Determinism requires:

- stable namespaced keys;
- explicit database ordering or in-memory stable sorting;
- deterministic frontier processing;
- deterministic truncation; and
- no dependence on unordered set or relationship iteration in the serialized
  result.

This supports reliable tests, caching decisions, exports, and future analysis
fingerprints.

## API shape

The planned generic route is:

```text
GET /api/operational-graph
```

See [`../product/release-c2-plan.md`](../product/release-c2-plan.md) for proposed
parameters and response fields.

The endpoint should use existing API conventions:

- Pydantic response models;
- explicit permission dependencies;
- central scope helpers;
- bounded query parameters;
- safe `404`/`403` behavior;
- no browser-only trust; and
- no commits or persistence for a read projection.

## Compatibility adapters

C2.1 should preserve:

```text
GET /api/services/{service_id}/graph
GET /api/business-functions/{function_id}/graph
```

These routes should call the shared builder and adapt its result to the current
`ServiceGraphResponse`. This proves shared semantics while avoiding an immediate
breaking change.

The current route-specific graph code should be removed only after the adapters
cover current behavior and regression tests pass.

## Query efficiency

The builder should avoid a database query per node or edge.

Preferred techniques:

- batch-load frontier edges;
- batch-load endpoint records by entity type;
- load Relationship Types into a keyed map;
- load completeness summaries and gap counts for all result nodes in bounded
  queries;
- use existing primary-key and active-edge indexes; and
- stop expansion before loading unnecessary deeper frontiers.

Correctness and authorization take precedence over caching. C2.1 should not use
Redis as a graph cache.

## Error and warning behavior

Safe warnings may include:

- node limit reached;
- requested edge family not supported for the focus type;
- historical reconstruction is partial because a current-only source model is
  present; and
- a viewable entity has incomplete knowledge.

Warnings must not name or count inaccessible entities.

Missing managed Relationship Type metadata should use a safe fallback label and
may emit a non-sensitive warning. The underlying operational edge should not be
silently reinterpreted.

## Extension to C2.2

Release C2.2 may add:

- dependency group IDs;
- group strategy (`all`, `any`, `minimum`);
- minimum available count;
- failure effect;
- optional/manual semantics; and
- completeness gaps for unclassified critical dependencies.

The C2.1 edge contract should be additive-friendly. Optional fields can be added
without changing node identity or current edge family keys.

## Extension to C2.3 and Release E

Release C2.3 should consume the shared graph through an internal contract rather
than requerying every table independently.

It adds:

- recursive analysis traversal;
- dependency-group evaluation;
- failure state propagation;
- explanation paths;
- reason codes;
- confidence qualification;
- unknown and potentially affected states; and
- analysis engine/schema versioning.

Release E adds the user-facing failure scenario and result workflow. The
operational graph remains the structural input; the analysis result is a
separate output.

## Extension to Release F

Planned-change simulation must use a scenario overlay rather than updating
accepted operational records.

A later scenario layer may:

1. load an accepted operational graph;
2. apply in-memory or persisted proposed mutations;
3. run the same analysis engine against the overlaid graph; and
4. preserve the scenario and immutable result separately.

C2.1 must not add scenario flags to current Assets or relationships as a shortcut.

## Relationship to B2 live discovery

C2.1 projects accepted operational records regardless of whether they were
created manually, through simulation and reconciliation, or through a future
live Integration run. It does not depend on completing B2 first.

However, C2.1 must not convert structural graph metadata into claims that an
Asset is currently responding, a source is fresh, a Service is healthy, or a
recovery path is available. Those conclusions require B2 freshness/telemetry and
later recovery and analysis semantics.

Integration CRUD, secret resolution, worker dispatch, scheduling, retries, and
live Proxmox execution remain outside the operational graph release.

## Data migration

C2.1 should require no graph persistence migration. It may add permission or
schema code only if necessary for the API contract, but the default plan is to
reuse existing permissions and tables.

C2.2 will likely need an additive migration for dependency semantics. That design
requires its own review and may require a new ADR if it changes operational
meaning or temporal behavior.

## Testing obligations

The release test plan is
[`../testing/release-c2-operational-graph.md`](../testing/release-c2-operational-graph.md).

At minimum, tests must cover:

- all node and edge families;
- semantic direction;
- namespaced identity;
- authorized and unauthorized focus;
- hidden endpoint non-disclosure;
- cross-customer/site substitution;
- current and historical temporal boundaries;
- cycles;
- deterministic ordering;
- node-limit truncation;
- compatibility of existing focused routes; and
- representative query performance.

## Operational non-goals

C2.1 does not prove:

- that an Asset is currently responding;
- that a Service is healthy;
- that a backup succeeded;
- that a recovery target is available;
- that an outage would propagate through a particular path;
- that a recovery will complete within RTO; or
- that a proposed change is safe.

Those claims require later operational evidence and analysis semantics.
