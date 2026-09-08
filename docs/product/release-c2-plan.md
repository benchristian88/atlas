# Release C2 implementation plan

Status: C2.1 complete; C2.2 complete; C2.3 complete; C2.4 next/planned

Latest implemented increment: **C2.3 — Explainable Dependency Analysis**

C2.3 adds `POST /api/dependency-analysis` and a small Preview unavailable panel
on Asset and Service details. It uses current authorized graph dependencies,
explicit effects, conservative aggregation, and structured paths without writes
or migrations. Subsequent live acceptance on the deployed PostgreSQL-backed
test LXC is complete for this lean scope. See
[the C2.3 validation and acceptance record](../testing/release-c2-explainable-dependency-analysis.md) and
[analysis architecture](../architecture/dependency-analysis.md).

## C2.1 implementation evidence — 3 September 2026

C2.1 was implemented in `a9f41df` and merged into `dev` by `1842d16` on
3 September 2026. The automated validation results recorded in
[`../testing/release-c2-operational-graph.md`](../testing/release-c2-operational-graph.md)
were collected on the feature working tree; the merge has the same tree as
`a9f41df`.

The original working-tree audit environment could not run PostgreSQL/Docker
acceptance. That audit limitation is preserved in the test plan and Feature
Ledger. Subsequent live pre-merge acceptance was completed in the deployed,
PostgreSQL-backed test LXC and covered:

- generic Asset, Service, and Business Function graph behavior;
- depth `0`, `1`, and `2`;
- incoming and outgoing traversal;
- edge-family filtering;
- safe node-limit truncation without dangling edges;
- Service→Service dependency traversal in both directions;
- preservation of semantic edge direction;
- cross-tenant non-disclosure using the normal “Record not found” response; and
- final migration and repository checks before merge.

The delivered implementation adds:

- `OperationalGraphBuilder`, a synchronous API/domain service with no FastAPI
  request dependency;
- typed namespaced node, edge, and response schemas;
- `GET /api/operational-graph` with Asset, Service, and Business Function focus,
  depth `0..2`, semantic direction, a hard node limit, and edge-family filters;
- per-node and per-edge permission/scope checks, including both-endpoint checks
  for grandfathered Asset relationships;
- request-time `valid_from <= generated_at < valid_to` filtering for temporal
  Service links;
- deterministic breadth-first expansion, cycle safety, deduplication, stable
  ordering, non-dangling truncation, and safe warnings;
- bounded batch loading for endpoints, Relationship Types, managed type labels,
  criticality, completeness summaries, and active gap counts;
- compatibility adapters used by both existing focused graph routes; and
- shared web normalization and an accessible graph-list presentation component
  used by the existing Service and Business Function pages.

The generic route excludes archived Services and inactive Business Functions by
default. The compatibility routes retain their existing ability to render an
archived/inactive focus record while excluding inactive adjacent records. The
generic contract uses `null` completeness and gap counts for Business Functions
because no Business Function completeness evaluator exists.

No migration, graph table, external graph service, cache, new permission, or
graph-rendering dependency was introduced.

## C2.2 implementation evidence — 8 September 2026

C2.2 is implemented on the feature working tree based on
`bd2ab6cacf7b6f11acad188827744f6105e50310`. The additive migration, API,
generic graph metadata, Service workflow, security tests, and PostgreSQL
upgrade/downgrade validation are recorded in
[`../testing/release-c2-lean-dependency-semantics.md`](../testing/release-c2-lean-dependency-semantics.md).

The implementation adds no permission, graph store, rule engine, worker, cache,
or consequence evaluator. `required_for_operation` and the existing dependency
routes remain available; their responses gain additive semantic fields.

### Subsequent live LXC acceptance

After that implementation-time validation, C2.2 completed manual acceptance in
the deployed PostgreSQL-backed test LXC. The upgrade preserved the existing
Reverse Proxy → DNS Service and DNS Service → Adguard Home Asset
dependencies without duplicates or fabricated groups. Required/Optional
compatibility and persistence, explicit failure-effect persistence, behaviour
removal with ungrouped fallback, and the mixed `Core Operation` Service→Asset
plus Service→Service group all passed.

The generic Operational Graph projected the mixed edges with one group identity,
`all`, `required`, `unavailable`, and compatible
`required_for_operation = true` metadata. Incoming traversal preserved the
canonical Reverse Proxy → DNS direction and semantics. A principal in another
tenant received the normal non-disclosing `{"detail":"Record not found"}`
response from the Service dependency-groups route.

The live topology had no genuine redundant AdGuard pair, so `any` was not
manually exercised and no fake topology was created. Automated C2.2 coverage
already exercises `any`. The implementation-time evidence and environment
limitations remain unchanged in the linked test record.

## C2.3 subsequent live LXC acceptance

C2.3 completed manual acceptance on the deployed PostgreSQL-backed test LXC:

- DNS unavailable made Reverse Proxy unavailable directly at 1 hop through
  `Core Operation`.
- AdGuard unavailable with ungrouped DNS semantics made DNS unknown at 1 hop
  and Reverse Proxy unknown downstream at 2 hops.
- After explicit `DNS Provider` semantics were configured, AdGuard unavailable
  made DNS unavailable at 1 hop and Reverse Proxy unavailable at 2 hops.
- PVE1 unavailable derived no Service consequence from current accepted C2.3
  dependency semantics. The structural AdGuard `Runs on` PVE1 relationship is
  not a failure rule; this result does not establish no real-world consequence.
- A principal in another tenant received **Record not found** on direct AdGuard
  Asset access; the analysis surface was unreachable and disclosed no analysis
  information. This is a security regression pass.

Explanations consumed persisted C2.2 semantics and retained actual C2.1
relationships and canonical direction. Nginx Proxy Manager remained unaffected
by the DNS/AdGuard scenarios, which is not a live-health claim.

`degraded`, `any`, cycles, truncation, site isolation and other cases identified
in the [C2.3 record](../testing/release-c2-explainable-dependency-analysis.md#subsequent-live-lxc-acceptance)
remain automated-only C2.3 coverage. That document separates these live results
from the unchanged implementation-time automated counts, commands, environment
limitations and original manual checklist. C2.4 is next/planned; this acceptance
does not complete F1-lite, B2-lite or Homelab Ready.

## Purpose

Release C2 converts the focused graph work delivered in C1 into a reusable,
secure, explainable foundation for the Homepage, Service Operations, Impact
Analysis, and Change Simulation.

The release is split into four increments:

- **C2.1 — Shared Operational Graph:** one API-owned structural graph projection
  over accepted operational records.
- **C2.2 — Lean Dependency Semantics:** required/optional meaning, `all`/`any`
  redundancy, and small explicit failure effects.
- **C2.3 — Explainable Dependency Analysis:** bounded consequence analysis,
  actual explanation paths, and small deterministic result states.
- **C2.4 — Homelab Operations Experience:** a polished dashboard, visual graph,
  enhanced Service Operations, exploration, and product refinement.

C2.1 is deliberately useful without attempting full impact analysis. The
near-term target is a Homelab Ready product, not completion of every later
enterprise domain model.

## Existing implementation to preserve

C2 builds on the following completed capabilities:

- central global/customer/site authorization and context filtering;
- accepted `Asset`, `AssetRelationship`, `Service`, and `BusinessFunction`
  records;
- temporal `ServiceAssetDependency`, `ServiceDependency`, and
  `ServiceBusinessFunction` records;
- managed Relationship Types and endpoint applicability;
- evidence, assertions, reconciliation, and meaningful `KnowledgeChange`
  history;
- Asset and Service completeness summaries and gaps;
- `/api/services/{id}/graph` and `/api/business-functions/{id}/graph` focused
  projections; and
- current Service and Business Function detail views.

C2.1 must preserve existing route behavior and C1 data. It should refactor graph
assembly internally before changing existing public response contracts.

At the pre-C2.1 baseline, the routes authorized focus records but differed in
adjacent-node checks. The delivered builder now applies endpoint-by-endpoint
non-disclosure while the compatibility adapters preserve public response
shapes.

## Governing architecture

Read these documents before implementation:

- [`../decisions/0001-shared-operational-graph.md`](../decisions/0001-shared-operational-graph.md)
- [`../architecture/operational-graph.md`](../architecture/operational-graph.md)
- [`../architecture/service-model.md`](../architecture/service-model.md)
- [`../architecture/service-dependencies.md`](../architecture/service-dependencies.md)
- [`../architecture/knowledge-changes-and-reconciliation.md`](../architecture/knowledge-changes-and-reconciliation.md)
- [`../architecture/knowledge-completeness.md`](../architecture/knowledge-completeness.md)

## Relationship to the repository ledger and other priorities

The pre-implementation readiness baseline was `dev` at
`4b0bfac6c746c56df9e1bfe16bae33d8dff3721e`, audited on 30 August 2026. The
C2.1 merge is `1842d161de87bcf826a15ae117703876fc30c192`; older audit points
remain historical comparison evidence and current code is authoritative.

Atlas is deliberately using manually entered and curated accepted knowledge for
the immediate development period. This lets C2.1 prove the knowledge, Service,
relationship, and graph models before major further investment in automatic
discovery and worker orchestration. B2 — Operational Integrations and live
discovery remains an incomplete parallel workstream, but it is not a C2.1
prerequisite.

C2.1 must remain separate from:

- Integration CRUD, secret resolution, worker dispatch, and live Proxmox runs;
- Documents API or Documents UI;
- removal or redesign of legacy `Asset.ip_address` handling; and
- automatic or assisted conversion of legacy Service-type Assets.

Those items remain visible in B2, F1, and the foundation-hardening backlog.

# C2.1 — Shared Operational Graph

## C2.1 outcome

A caller can request a focused graph for an authorized Asset, Service, or
Business Function and receive a deterministic typed projection assembled by one
shared domain service.

The projection describes structure and accepted operational context. It does
not claim outage propagation, recovery availability, or a global confidence
score.

It may answer structural questions such as what is connected, which Services
use an Asset, what Assets support a Service, which Services depend on another
Service, which Business Functions are linked, and what bounded path joins known
entities. It must not label reachability as outage blast radius, failure
probability, recovery order, business severity, protection adequacy, a single
point of failure, or change safety.

## C2.1 scope

### In scope

- typed graph node and edge schemas;
- a stable graph identity format;
- a reusable graph builder in the FastAPI application;
- loaders for current Asset, Service, and Business Function edge families;
- current-valid temporal filtering at one captured request time;
- authorization filtering at every expansion boundary;
- bounded focused projection;
- cycle-safe traversal and deduplication;
- deterministic result ordering;
- explicit truncation and warnings;
- a generic graph route;
- compatibility adapters for existing focused graph routes;
- reusable web graph normalization/presentation primitives;
- automated API, authorization, and regression tests; and
- updated architecture, testing, and feature documentation after delivery.

### Out of scope

- a graph database or materialized second source of truth;
- dependency groups, quorum, or redundancy evaluation;
- failure propagation and blast-radius conclusions;
- scenario persistence or intended-state overlays;
- recovery path selection or restoration estimates;
- live monitoring or telemetry ingestion;
- Integration CRUD, secret resolution, worker dispatch, or live Proxmox runs;
- Documents API or Documents UI;
- removal or redesign of legacy `Asset.ip_address` handling;
- automatic or assisted conversion of legacy Service-type Assets;
- formal People/Team ownership;
- Knowledge Objects; and
- a redesigned Homepage, Impact Analysis page, or Change Simulation page.

Caller-selected historical graph projection is also out of scope. It may be
added later after every source model can state its historical limitations
honestly.

A small Service Operations graph improvement may consume C2.1, but the release
should be judged by the shared foundation rather than a large UI redesign.

## Proposed graph identity

UUIDs are not sufficient as graph keys because different entity tables may
legitimately contain the same UUID value. Use a namespaced key:

```text
asset:<uuid>
service:<uuid>
business_function:<uuid>
```

Edges should also have a namespaced key:

```text
asset_relationship:<uuid>
service_asset:<uuid>
service_service:<uuid>
service_business_function:<uuid>
```

The response may retain `entity_id` or `edge_id` as UUID fields, but graph joins,
deduplication, and web rendering should use the namespaced key.

## Proposed graph contract

The exact Pydantic names may follow repository conventions, but the contract
should carry equivalent information.

```python
class OperationalGraphNode(BaseModel):
    key: str
    entity_type: Literal["asset", "service", "business_function"]
    entity_id: UUID
    customer_id: UUID
    site_id: UUID | None
    name: str
    subtitle: str | None
    href: str
    lifecycle_state: str | None
    operational_state: str | None
    criticality_key: str | None
    criticality_name: str | None
    completeness_status: str | None
    open_gap_count: int
    source: str | None
    updated_at: datetime | None

class OperationalGraphEdge(BaseModel):
    key: str
    edge_family: Literal[
        "asset_relationship",
        "service_asset",
        "service_service",
        "service_business_function",
    ]
    edge_id: UUID
    source_key: str
    target_key: str
    relationship_type_key: str | None
    relationship_type_name: str | None
    label: str
    required_for_operation: bool | None
    valid_from: datetime | None
    valid_to: datetime | None
    source: str | None
    knowledge_state: Literal["accepted"]

class OperationalGraphResponse(BaseModel):
    focus_key: str
    generated_at: datetime
    requested_depth: int
    truncated: bool
    warnings: list[str]
    nodes: list[OperationalGraphNode]
    edges: list[OperationalGraphEdge]
```

C2.1 should not add a numeric `confidence` field unless a documented formula and
source data exist. It may expose completeness status, gap count, source, and
freshness metadata so later releases can calculate qualified confidence.

## Proposed API

Add a dedicated router, for example:

```text
GET /api/operational-graph
```

Initial query parameters:

| Parameter | C2.1 behavior |
| --- | --- |
| `focus_type` | Required: `asset`, `service`, or `business_function` |
| `focus_id` | Required UUID |
| `max_depth` | Default `1`; allowed `0..2` for structural projection |
| `direction` | `both`, `outgoing`, or `incoming`; default `both` |
| `node_limit` | Default `250`; hard maximum `500` unless profiling justifies another limit |
| `edge_family` | Optional repeated or comma-separated family filter |

The active customer/site context may further narrow results, but it does not
prove authorization. The API must first authorize the focus entity and must
apply per-entity permissions to every node and edge.

Suggested permission behavior:

- `asset` focus requires `assets.view`;
- `service` focus requires `services.view` and uses
  `service_dependencies.view` for dependency expansion;
- `business_function` focus requires `business_functions.view`;
- an endpoint is included only when the principal can view that entity type in
  its customer/site scope; and
- no warning, count, dangling edge, or truncation total may reveal an inaccessible
  entity.

Do not add a broad `graph.view_all` permission in C2.1 merely to simplify the
route. Reuse the explicit existing permissions unless a later security review
finds a concrete need for a new permission.

## Source-to-graph mapping

| Graph element | Current source | C2.1 rule |
| --- | --- | --- |
| Asset node | `Asset` | Include accepted operational record only when viewable |
| Service node | `Service` | Exclude archived Services by default unless explicitly requested later |
| Business Function node | `BusinessFunction` | Include active records by default |
| Asset to Asset edge | `AssetRelationship` plus managed Relationship Type by stable key | Preserve stored source/target direction and current authorization rules |
| Service to Asset edge | `ServiceAssetDependency` | Include when valid at the captured request time; carry `required_for_operation` |
| Service to Service edge | `ServiceDependency` | Include when valid at the captured request time; preserve legitimate cycles |
| Service to Business Function edge | `ServiceBusinessFunction` | Include when valid at the captured request time |
| Completeness metadata | `KnowledgeCompletenessSummary` and active `KnowledgeGap` counts | Load in bounded batches rather than per-node queries |
| Relationship labels | `RelationshipType` | API supplies semantic labels; web does not infer meaning from keys |

Asset relationships do not currently have the same temporal `valid_from` and
`valid_to` contract as C1 Service links. C2.1 therefore projects current Asset
relationships and current-valid Service links. It does not offer historical
reconstruction. A later model change can add temporal Asset relationships
through an additive migration and ADR if needed.

Incoming and outgoing filters describe how traversal reaches an edge relative
to its canonical stored source and target. Reverse traversal never swaps
`source_key` and `target_key`, changes the Relationship Type, or substitutes an
inverse label as the edge's semantic meaning. Presentation may additionally
show an API-provided inverse label without changing canonical direction.

## Internal implementation shape

A minimal implementation can follow existing flat service/router conventions:

```text
apps/api/app/services/operational_graph.py
apps/api/app/routes/operational_graph.py
apps/api/app/schemas.py
apps/api/app/main.py
apps/api/tests/test_operational_graph.py
```

The domain service should not import FastAPI request objects. It should accept a
validated principal/request context or explicit scope predicate and a projection
request.

Suggested internal responsibilities:

```text
OperationalGraphBuilder
├── resolve and authorize focus
├── load initial node
├── load eligible edge families in batches
├── authorize endpoints before inclusion
├── apply current-valid and active-state rules
├── deduplicate by namespaced key
├── stop at depth and node limits
├── sort deterministically
└── return warnings and truncation state
```

The first implementation may remain synchronous with SQLAlchemy because the
current API uses synchronous sessions. Do not introduce a new persistence or
async framework solely for this release.

## Existing route compatibility

The following endpoints must remain usable:

```text
GET /api/services/{service_id}/graph
GET /api/business-functions/{function_id}/graph
```

Recommended approach:

1. Build the new graph service and generic contract.
2. Add adapter functions that convert a shared graph result to the existing
   `ServiceGraphResponse` shape.
3. Replace the route-owned graph assembly in `routes/services.py` and
   `routes/business_functions.py` with calls to the builder plus adapter.
4. Keep the old response schemas and frontend callers unchanged during C2.1.
5. Migrate web pages to the new generic contract only in a separate, testable
   change.
6. Deprecate an old contract only after all callers are migrated and release
   notes document the change.

This sequence reduces risk and proves that both current routes use the same
semantics.

## Projection algorithm

A C2.1 projection is structural breadth-first expansion, not impact analysis.

Pseudocode:

```text
authorize focus
add focus node
queue (focus, depth 0)

while queue is not empty:
    take next entity in deterministic order
    if depth == max_depth: continue
    load permitted edge families valid at the captured request time
    for each edge in deterministic order:
        resolve source and target
        if either endpoint is not viewable: omit the complete edge silently
        add authorized nodes and edge using namespaced keys
        queue newly added endpoints at depth + 1
        if node limit reached:
            set truncated and stop expansion deterministically

sort nodes and edges by stable keys
return result
```

Cycles are permitted. The visited set prevents repeated expansion; it must not
remove a legitimate edge merely because both endpoint nodes already exist.

## Query and performance rules

C2.1 should avoid obvious N+1 behavior:

- load Relationship Types into a keyed map for the result scope;
- batch-load node metadata and completeness summaries;
- batch-load edges for the current frontier where practical;
- use existing indexed IDs and active-link predicates;
- preserve a hard result limit;
- return explicit truncation instead of silently dropping arbitrary rows; and
- add query-count or performance regression coverage for the representative
  homelab fixture.

Do not introduce Redis caching in C2.1. Correctness, authorization, and contract
stability come first. Consider caching only after profiling, with cache keys that
include principal authorization, customer/site context, query shape, current
data version/freshness boundaries, and a safe invalidation strategy.

## Web implementation

Add shared, presentation-neutral graph utilities rather than another screen-
specific graph implementation.

Possible files:

```text
apps/web/lib/operational-graph.mjs
apps/web/components/operational-graph-view.js
apps/web/tests/operational-graph.test.mjs
```

The web layer should:

- use `node.key`, `source_key`, and `target_key` for graph identity;
- render API-provided labels;
- preserve semantic direction even when layout places nodes visually in another
  order;
- show truncation and unknown metadata visibly;
- link to API-provided `href` values;
- apply no impact, confidence, or severity logic; and
- remain usable with keyboard and responsive layouts.

A graph rendering library is optional. Adding a large dependency is not a C2.1
requirement if the current components can render the focused result clearly.

## Manual reference environment

C2.1 development and demos should use the manually populated fixture in
[`../testing/release-c2-operational-graph.md`](../testing/release-c2-operational-graph.md).
Every required record can be created with the current Atlas UI/API: Assets,
Services, Business Functions, Asset relationships, and all three C1 temporal
link families. The fixture includes an Application Asset, multiple upstream and
downstream branches, a legitimate Service cycle, and customer/site isolation
cases. It is test/demo guidance, not a production taxonomy or a dependency on
plugin discovery.

## C2.1 delivered implementation sequence

| ID | Work item | Main outcome |
| --- | --- | --- |
| C2.1-01 | Accept ADR and documentation baseline | Shared direction is explicit before code changes |
| C2.1-02 | Add graph identity helpers and schemas | Stable namespaced node/edge contract |
| C2.1-03 | Add source loaders | Existing four edge families project through one interface |
| C2.1-04 | Implement builder | Bounded, cycle-safe, deterministic, scope-aware graph |
| C2.1-05 | Add generic API route | Authorized focused structural graph available to future views |
| C2.1-06 | Add authorization and IDOR tests | No cross-customer/site/entity leakage |
| C2.1-07 | Refactor Service graph route | Existing route uses builder with unchanged contract |
| C2.1-08 | Refactor Business Function graph route | Existing route uses builder with unchanged contract |
| C2.1-09 | Add shared web normalization/view | Reusable rendering foundation |
| C2.1-10 | Regression and performance validation | Existing C1, topology, knowledge, and build checks remain green |
| C2.1-11 | Update ledger and release notes | Implementation state is re-audited at a named commit |

These items were delivered in `a9f41df` and merged by `1842d16`. The change
contains no UI redesign or data-model migration.

## C2.1 acceptance criteria

C2.1 is complete when:

- a shared graph builder exists and is used by both current focused graph routes;
- the generic graph route supports authorized Asset, Service, and Business
  Function focus;
- nodes and edges use namespaced graph keys;
- semantic source/target direction is preserved;
- current temporal Service links are filtered correctly at the captured request
  time;
- cycles do not loop or remove valid edges;
- duplicate rows do not create duplicate graph objects;
- result ordering is deterministic;
- limits produce an explicit, stable truncation result;
- inaccessible endpoints, labels, counts, and dangling edges are absent;
- no accepted operational row is duplicated into a new graph persistence table;
- current Service and Business Function pages continue to work;
- the existing API, web, plugin, migration, and production-build validations
  pass; and
- the feature ledger is re-audited without claiming tests that were not run.

# C2.2 — Lean Dependency Semantics

## Purpose

C1 records whether a Service dependency is required for operation. Homelab
consequence analysis needs a small amount of additional meaning for optional
dependencies, basic redundancy, degradation, and unknown cases.

C2.2 adds explicit semantics before full impact propagation.

## Homelab scope

The model must support:

```text
dependency requirement: required | optional
redundancy strategy: all | any
failure effect: unavailable | degraded | unknown
```

The implemented additive schema uses temporal `dependency_groups` and
`dependency_group_memberships`. A group belongs to one Service and records the
small vocabulary above. Memberships can reference existing Service→Asset and
outgoing Service→Service rows, including a mixed set, without replacing those
authoritative relationships. Important constraints are:

- current rows remain valid after migration;
- current `required_for_operation` consumers remain compatible;
- a default migration must not reinterpret optional dependencies as critical;
- unknown semantics remain explicit without automatically creating Knowledge
  Gaps;
- any groups or memberships preserve history; and
- relationship direction remains independent from propagation direction.

## Explicit enterprise deferrals

C2.2 does not require `minimum`, quorum, `minimum_available`, weighted rules,
conditional rules, rich recovery preference, or a general dependency-group
language. The design should leave additive extension points for those later
capabilities without implementing them for Homelab Ready.

## C2.2 acceptance themes

- required and optional dependencies;
- `all` and `any` fixtures;
- optional monitoring dependency causing degradation rather than outage;
- storage dependency required for one Service but optional for another;
- unresolved semantics producing `unknown`;
- safe additive migration; and
- clear UI wording that does not imply a live health signal.

Implemented API/UI surface:

- `GET|POST /api/services/{service_id}/dependency-groups`;
- `PATCH|DELETE /api/dependency-groups/{group_id}`;
- additive semantic fields on both dependency response types and applicable
  generic Operational Graph edges; and
- compact dependency-set creation and editing on Service detail.

Group updates use temporal supersession. Existing ungrouped rows are not
backfilled: their required/optional meaning continues to come from
`required_for_operation`, and their failure effect is safely `unknown`.

# C2.3 — Explainable Dependency Analysis

## Purpose

C2.3 consumes the graph and lean dependency semantics to answer useful homelab
questions: which known Services may be affected when an Asset or Service is
unavailable, whether the consequence is direct or downstream, why Atlas reached
that conclusion, and where semantics are too incomplete to decide.

## Analysis contract (implemented C2.3)

```text
POST /api/dependency-analysis
- focus_type: asset | service
- focus_id
- state: unavailable
- max_depth, max_results, max_paths_per_result

DependencyAnalysisResponse
- focus_key, focus, analysis_time, scenario_state, assumption
- schema_version, engine_version
- truncated, warnings
- results: service, state, classification, distance, reasons, paths
```

## Required behaviors

- deterministic recursive traversal;
- cycles terminate safely;
- `all` and `any` dependency sets are evaluated with stable rules;
- results use `unavailable`, `degraded`, `unknown`, and `unaffected` only where
  defensible;
- missing semantics yield `unknown`, not a fabricated outage or probability;
- each conclusion carries one or more explanation paths;
- scope is enforced before and during traversal; and
- the domain engine is independent of HTTP and frontend rendering; intended-state
  overlays and additional scenarios remain deferred.

## C2.3 non-goals

- complete recovery workflow;
- exact restoration duration without D2 evidence;
- change approval and execution;
- AI-generated remediation; and
- operational telemetry ingestion.

C2.3 is not a general enterprise reasoning or confidence-scoring framework.

# C2.4 — Homelab Operations Experience

## Purpose

C2.4 turns the C1/C2 technical foundation into a polished, highly visual
product. It is a major product release rather than cosmetic cleanup.

## Product outcomes

- a beautiful operational homepage using defensible real Atlas data to explain
  the environment, what matters, what Atlas knows, and what needs attention;
- a polished interactive Knowledge Graph over the existing C2.1 API, with
  distinct entity types, semantic direction, focus/navigation, bounded depth
  and edge filters where useful, responsive behavior, accessibility, and clear
  empty/truncated states;
- enhanced Service Operations showing providers, dependencies, dependants,
  supported Business Functions, criticality, completeness, unknown semantics,
  and C2.3 consequence information where available;
- natural Asset → Service → Business Function → infrastructure exploration; and
- deliberate hierarchy, spacing, loading/empty states, terminology, theme
  compatibility, and Atlas Impact branding.

The API remains authoritative for graph membership, relationship semantics,
authorization, and dependency conclusions. The browser may lay out and filter
authorized results but must not become an impact engine. Dashboard summaries
must not imply live health without live evidence.

## Relationship to Homelab Ready

After C2.4, the principal product path continues through F1-lite Homelab
Documentation, B2-lite Live Proxmox Discovery, and Homelab Ready hardening. C3
People/Teams, C4 formal Knowledge Objects, advanced recovery, richer dependency
semantics, full enterprise Impact Analysis, and intended-state simulation are
not C2 acceptance requirements. See
[`development-roadmap.md`](development-roadmap.md) for the canonical sequence.

# Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Graph logic becomes another truth store | Derive from operational tables; no C2.1 graph persistence |
| Existing screens break during refactor | Keep compatibility adapters and migrate callers separately |
| Generic route leaks inaccessible context | Authorize focus and every endpoint; test IDs, counts, edges, and warnings |
| UI invents semantics | API returns labels and metadata; UI performs layout only |
| C2.1 expands into full impact analysis | Enforce release non-goals and acceptance criteria |
| N+1 queries make graphs slow | Batch frontier, type, and completeness loads; profile representative fixtures |
| UUID collisions across entity types | Use namespaced graph keys |
| Historical query implies unsupported Asset history | Document current Asset relationship limitation; do not invent temporal data |
| Confidence is misleading | Use explicit paths and `unknown`; defer elaborate confidence/scoring to later enterprise work |
| C2.2 migration changes current meaning | Additive nullable semantics with conservative defaults and migration tests |

# Historical C2.1 implementation checklist

This checklist guided the delivered implementation:

1. Read the ADR, operational graph architecture, this plan, and the current
   graph route implementations.
2. Confirm the current branch, commit, migration head, and readiness audit;
   report material differences and treat current code as authoritative.
3. Create the graph identity helpers and response schemas with tests first.
4. Implement a builder that reproduces the current Service graph result for the
   representative C1 fixture.
5. Refactor only the Service graph route and run regressions.
6. Refactor the Business Function graph route.
7. Add the generic route and explicit authorization cases.
8. Add shared web utilities only after API contracts are stable.
9. Confirm that B2 Integration work, Documents UI, Interface-first IP cleanup,
   and legacy Service Asset conversion have not entered the C2.1 change set.
10. Run all supported tests and builds.
11. Update the feature ledger at the delivered commit.
