# ADR-0001: Preserve the relational system of record and add a derived operational graph

- Status: Accepted
- Date: 4 August 2026
- Decision scope: Release C2.1 and the graph/analysis foundation for later releases

## Clarification — 30 August 2026

The immediate product sequence is manual-first: accepted manually curated
Assets, Services, Business Functions, and relationships are sufficient C2.1
input. B2 live discovery is not a prerequisite.

C2.1 is a current operational projection. It captures one request time and
filters temporal Service links against it, but does not expose caller-selected
historical `as_of` reconstruction. References below to `as_of` describe an
approved extension point for a later feature, not C2.1 scope. This clarification
narrows delivery scope without changing the original system-of-record,
identity, authorization, compatibility, or structural-versus-analysis decision.

## Delivery and sequencing note — 3 September 2026

C2.1 is implemented and merged. The current roadmap narrows C2.2 to lean
homelab dependency semantics (`all`/`any` plus small explicit failure effects)
and reframes C2.3 as explainable dependency analysis. References below to
minimum counts, quorum, rich confidence qualification, or complete Impact
Analysis describe additive later enterprise extensions, not Homelab Ready
acceptance criteria. This product-sequencing refinement does not change this
ADR's accepted system-of-record, graph identity, authorization, compatibility,
or structural-versus-analysis decisions.

## Context

Atlas has completed the platform and inventory foundation, Release A Knowledge
Foundation, the core of Release B discovery simulation and reconciliation,
Release B.5 knowledge completeness for Assets and Services, and Release C1
Homelab Service MVP.

Those releases established important architectural behavior:

- PostgreSQL holds the durable operational model.
- FastAPI owns authentication, authorization, validation, scope, and persistence.
- customer/site isolation applies to objects, lists, counts, topology, and direct
  ID substitution;
- evidence, assertions, reconciliation items, accepted operational records,
  knowledge changes, and knowledge gaps are separate concepts;
- first-class Services remain distinct from technical Assets;
- Service-to-Asset, Service-to-Service, and Service-to-Business Function links
  preserve semantic direction and temporal history;
- managed Relationship Types provide stable keys, labels, and endpoint
  applicability; and
- existing Service and Business Function graph routes provide useful but
  route-owned focused projections.

The next product concepts — the enhanced Homepage, Service Operations, Impact
Analysis, and Change Simulation — all require graph-shaped operational context.
Implementing each view independently would duplicate relationship logic,
permission checks, graph identity, temporal filtering, and later impact rules.
That would make conclusions inconsistent and increase the risk of scope leakage.

A graph database could provide native traversal, but Atlas does not yet have a
scale or query requirement that justifies introducing a second persistence
technology and synchronization boundary. The current relational records already
contain the accepted operational model required for the next increment.

## Decision

Atlas will introduce a **shared operational graph projection** in the FastAPI API
for Release C2.1.

### 1. PostgreSQL remains the canonical system of record

Assets, Asset relationships, Services, Service dependencies, Business
Functions, assertions, completeness records, and later scenario records remain
in the relational model unless a future ADR explicitly changes that decision.

C2.1 will not create a materialized graph table or external graph database.

### 2. The graph is derived at read time

A reusable API/domain service will load accepted operational records and project
them into typed nodes and edges. The projection is a read model and is not
independently editable.

### 3. Accepted operational knowledge is the default input

Unaccepted source-current assertions and raw discovery evidence will not appear
as operational edges by default. The graph may expose bounded provenance,
source, freshness, completeness, and knowledge-gap qualifiers.

A later analysis release may deliberately compare accepted state with observed
or intended state, but those states remain distinct.

### 4. The API owns graph semantics and authorization

The API will provide:

- namespaced node and edge identity;
- semantic source and target direction;
- managed relationship labels;
- active and `as_of` temporal filtering where supported;
- per-entity permission and customer/site scope checks;
- deterministic ordering and bounded projection;
- cycle-safe expansion;
- explicit truncation and safe warnings; and
- compatibility adapters for current graph endpoints.

The web UI may layout and present the graph. It will not become the authority for
relationship meaning, impact, confidence, severity, or hidden-node filtering.

### 5. Existing graph endpoints remain compatible during C2.1

`GET /api/services/{id}/graph` and
`GET /api/business-functions/{id}/graph` will continue to return their current
contracts while their implementation is refactored to call the shared graph
builder.

A generic operational graph contract may be added for future product views.
Existing callers will be migrated separately before any deprecation.

### 6. C2.1 is structural, not analytical

C2.1 will not decide outage propagation, recovery availability, restoration
duration, business impact, or planned-change safety.

Release C2.2 will add lean dependency semantics: required/optional meaning,
`all`/`any` redundancy, and explicit unavailable/degraded/unknown failure
effects. Release C2.3 will add bounded analysis traversal and path explanation.
Later enterprise releases may add quorum, richer dependency rules, confidence
qualification, recovery evidence, broader Impact Analysis, scenarios, and
intended state.

### 7. Hypothetical state remains separate from accepted state

Later failure or change scenarios will be applied as an overlay to a graph
snapshot or query result. A simulation must not update accepted Assets,
relationships, Services, assertions, or operational state merely to perform an
analysis.

## Consequences

### Positive

- The Homepage, Service Operations, Impact Analysis, and Change Simulation can
  consume one consistent graph foundation.
- Existing relational data and migrations remain authoritative and additive.
- Authorization and non-disclosure behavior remain in the API boundary.
- Current C1 graph routes can be refactored without an immediate breaking API
  change.
- Namespaced identity prevents cross-entity UUID ambiguity.
- Later analysis can reuse stable structural contracts rather than reimplementing
  database queries for each workflow.
- The design remains suitable for a homelab while preserving multi-customer MSP
  isolation.

### Negative

- Relational traversal requires careful batching and may be less efficient than
  a native graph database for very large, deep graphs.
- The API must maintain adapters while old and new contracts coexist.
- Current Asset relationships do not provide the same temporal history as C1
  Service links, so historical graph reconstruction is partial.
- Provenance and confidence cannot be reduced to a simple number without further
  modelling and documented rules.
- C2.1 will not immediately deliver the visually complete Impact Analysis or
  Change Simulation concepts.

### Risks

- A route-specific implementation may bypass the shared builder.
- A generic graph route may accidentally disclose inaccessible endpoints or
  counts.
- Performance may degrade through N+1 queries.
- UI code may reintroduce hard-coded relationship semantics.
- Later developers may mistake a structural path for a failure-propagation rule.

These risks are addressed through compatibility refactoring, explicit test
plans, batch loading, API-provided labels, release boundaries, and documentation.

## Alternatives considered

### Build each product screen independently

Rejected. It would duplicate graph assembly, authorization, and later analysis
rules. Results could disagree between the Homepage, Service detail, Impact
Analysis, and Change Simulation.

### Introduce a graph database now

Rejected for C2.1. It would add deployment, synchronization, migration,
consistency, authorization, backup, and operator complexity without a proven
scale requirement. It may be reconsidered only after profiling demonstrates a
need that cannot be met safely in PostgreSQL.

### Materialize a graph projection in PostgreSQL

Deferred. A materialized read model may become useful for performance, immutable
analysis snapshots, or event-driven refresh. C2.1 first establishes the contract
and correctness of a derived graph. Any materialization requires an invalidation
and migration design.

### Build the graph entirely in the web application

Rejected. The browser is untrusted and cannot be the authorization boundary.
Frontend assembly would also duplicate semantic and temporal logic.

### Use all source-current assertions as graph edges

Rejected. Source-current and accepted are independent states. Including
unaccepted observations in the operational graph would bypass reconciliation and
change the meaning established in Release A and B.

### Replace current Service graph endpoints immediately

Rejected. A breaking replacement would combine architecture work with caller
migration and increase release risk. Compatibility adapters provide a safer path.

## Compatibility and migration

C2.1 should require no graph persistence migration. Existing operational rows
remain unchanged.

The implementation should:

1. add graph identity and response contracts;
2. add the shared builder and generic route;
3. adapt the current Service and Business Function graph routes;
4. preserve existing response shapes until callers are migrated;
5. run current API, web, plugin, migration, and build checks; and
6. update the feature ledger at the delivered commit.

C2.2 may require an additive dependency-semantics migration and a follow-up ADR
if the chosen design changes the meaning or lifecycle of existing dependency
records.

## Validation

The decision is validated when C2.1 demonstrates that:

- both existing focused graph routes use the shared builder;
- a generic focused graph can project Assets, Services, and Business Functions;
- no cross-customer/site or mixed-permission information is exposed;
- cycles and limits are deterministic;
- current temporal Service links are filtered correctly;
- existing callers remain functional; and
- no second graph persistence store has been introduced.

See
[`../testing/release-c2-operational-graph.md`](../testing/release-c2-operational-graph.md).

## Review triggers

Revisit this decision if one or more of the following becomes true:

- representative scoped graphs cannot meet agreed latency or memory targets
  after relational query optimization;
- required analysis depth or graph size makes request-time projection
  impractical;
- immutable historical graph snapshots become a core compliance requirement;
- multiple services need a durable event-driven graph read model;
- authorization cannot be expressed safely and efficiently over the current
  projection; or
- a new source of truth is proposed for accepted operational relationships.

A performance concern alone does not authorize an unreviewed graph database or
cache. Record the evidence and create a superseding ADR.
