# Codex prompt — Release C2.1 Shared Operational Graph

Copy the complete prompt below into Codex from the Atlas repository root.

```text
You are working in the Atlas repository.

Repository:
https://github.com/benchristian88/atlas

Starting branch:
dev

Development objective:
Implement Release C2.1 — Shared Operational Graph.

This is an implementation task, not a roadmap or exploratory design task. The
repository documentation defines the approved direction, but the current source
code is authoritative where later commits differ from the documented audit
baseline.

The current feature-ledger audit baseline is:

- branch: dev
- commit: 09d2271
- audit date: 23 July 2026
- review date: 24 July 2026

Confirm whether the current working branch is still at that baseline or contains
later changes. Treat later repository code as authoritative and report any
material differences before implementation.

C2.1 has deliberately been selected as the next development increment so that
the Homepage, Service Operations, Impact Analysis, and future Change Simulation
views can share one graph foundation. This is a sequencing decision, not a
change to repository status.

B2 — Operational Integrations and live discovery remains the largest incomplete
end-to-end operational journey and may progress as a separate parallel
workstream. Do not include B2 work in the C2.1 change set.

Create a feature branch named:

feature/c2-1-shared-operational-graph

Do not push changes to GitHub. Do not merge into dev. Do not rewrite unrelated
code.

----------------------------------------------------------------------
1. READ AND VERIFY THE REPOSITORY BEFORE CODING
----------------------------------------------------------------------

Before making changes, read the relevant repository documentation, including:

- docs/README.md
- docs/product/feature-ledger.md
- docs/product/development-roadmap.md
- docs/product/release-c2-plan.md
- docs/product/mvp-brief.md
- docs/architecture/architecture-v0.md
- docs/architecture/operational-graph.md
- docs/architecture/service-model.md
- docs/architecture/service-dependencies.md
- docs/architecture/knowledge-changes-and-reconciliation.md
- docs/architecture/knowledge-completeness.md
- docs/decisions/0001-shared-operational-graph.md
- docs/testing/release-c2-operational-graph.md
- docs/testing/security-and-access-test-plan.md
- docs/prompts/atlas-codex-context.md

Also inspect all other relevant architecture, testing, and development documents
under /docs.

Then inspect the current implementation of:

- Asset models, schemas, routes, and permissions
- AssetRelationship and RelationshipType handling
- Service models, schemas, and routes
- ServiceAssetDependency
- ServiceDependency
- ServiceBusinessFunction
- BusinessFunction models, schemas, and routes
- KnowledgeCompletenessSummary
- KnowledgeGap
- authentication, customer, and site authorization
- request context and workspace filtering
- existing graph APIs
- existing graph frontend components
- API and web test fixtures
- repository test and build commands

In particular, inspect the current implementations of:

- GET /api/services/{service_id}/graph
- GET /api/business-functions/{function_id}/graph

Do not assume the planning documents perfectly reflect every current filename or
implementation detail. Verify the code and follow established repository
conventions.

Before coding, provide a concise implementation assessment containing:

1. The current branch, commit, and migration head.
2. Whether the repository differs materially from the 09d2271 ledger baseline.
3. The existing graph-related implementation you found.
4. The files you expect to add or change.
5. Any differences between the documents and current code.
6. The logical implementation sequence.
7. Any genuine blocker that prevents C2.1 from being implemented.

Unless there is a material architectural or security blocker, continue directly
into implementation after the assessment. Do not stop merely to request approval
for routine implementation choices.

----------------------------------------------------------------------
2. ARCHITECTURAL BOUNDARIES
----------------------------------------------------------------------

Preserve all architectural decisions already established in Releases A through
C1.

The following are non-negotiable:

- PostgreSQL remains the durable source of truth.
- FastAPI remains responsible for authentication, authorization, scope,
  validation, and persistence.
- The operational graph is a derived read-time projection.
- Do not introduce a graph database.
- Do not introduce a materialized graph persistence table.
- Do not duplicate accepted operational records into a second graph store.
- Only accepted operational knowledge is included by default.
- Discovery evidence or unaccepted assertions must not silently appear as
  accepted graph nodes or edges.
- Customer and site isolation must apply at every graph expansion boundary.
- The selected customer/site workspace context must not be treated as proof of
  authorization.
- Existing global/customer/site assignment rules must remain intact.
- Existing graph endpoint contracts must remain compatible during C2.1.
- Do not add a broad graph.view_all permission merely to simplify
  implementation.
- Do not introduce Redis or graph caching in this release.
- Do not add impact-analysis, recovery, severity, or confidence conclusions in
  the web layer.
- Do not infer relationship semantics from hard-coded frontend key lists.
- Do not implement C2.2 or C2.3 as part of this task.

C2.1 is structural graph projection only.

Explicitly out of scope:

- dependency groups;
- quorum evaluation;
- redundancy evaluation;
- outage propagation;
- blast-radius conclusions;
- scenario persistence;
- intended-state overlays;
- change simulation;
- recovery-path selection;
- restoration-time estimates;
- live monitoring or telemetry;
- People and Teams;
- formal Knowledge Objects;
- Homepage redesign;
- Impact Analysis workflow;
- Change Simulation workflow;
- Backup and Recovery implementation;
- Integration CRUD;
- secret-reference resolution;
- Test Connection or Run Now workflows;
- worker dispatch, retries, cancellation, or scheduling;
- live Proxmox execution;
- Documents API or Documents UI;
- removal or redesign of legacy Asset.ip_address handling;
- Interface-first IP cleanup;
- automatic or assisted conversion of legacy Service-type Assets.

----------------------------------------------------------------------
3. IMPLEMENT C2.1 — SHARED OPERATIONAL GRAPH
----------------------------------------------------------------------

Implement one reusable API-owned operational graph builder that supports focused
structural projections for:

- Asset
- Service
- Business Function

Use the repository's current synchronous SQLAlchemy and FastAPI conventions
unless the existing code clearly uses another established pattern.

The builder must not depend on FastAPI request objects directly. It should
receive validated context, authorization information, and projection parameters
through an explicit interface.

A reasonable implementation shape is:

- apps/api/app/services/operational_graph.py
- apps/api/app/routes/operational_graph.py
- graph-related schemas in the repository's established schema location
- route registration in the existing API application setup
- API tests in the established tests directory

Adapt paths and filenames to repository conventions where necessary.

The shared builder should be responsible for:

- resolving the focus entity;
- authorizing the focus entity;
- loading the focus node;
- expanding eligible edge families;
- authorizing every endpoint before inclusion;
- applying active-state and as-of-time rules;
- preserving stored semantic source and target direction;
- deduplicating nodes and edges;
- handling legitimate cycles;
- enforcing projection depth;
- enforcing node limits;
- deterministic traversal;
- deterministic result ordering;
- safe truncation;
- safe warnings;
- returning a typed graph result.

----------------------------------------------------------------------
4. GRAPH IDENTITY
----------------------------------------------------------------------

Use namespaced graph keys.

Node keys:

- asset:<uuid>
- service:<uuid>
- business_function:<uuid>

Edge keys:

- asset_relationship:<uuid>
- service_asset:<uuid>
- service_service:<uuid>
- service_business_function:<uuid>

Do not use raw UUIDs alone as graph identity because UUID uniqueness is not
guaranteed across separate entity tables.

Retain the underlying UUID separately for API links and entity operations.

----------------------------------------------------------------------
5. GRAPH CONTRACT
----------------------------------------------------------------------

Implement typed node, edge, and response schemas equivalent to those documented
in:

docs/product/release-c2-plan.md

At minimum, graph nodes should expose:

- namespaced key;
- entity type;
- entity UUID;
- customer ID;
- site ID where applicable;
- name;
- subtitle or type label where available;
- API-provided href;
- lifecycle state where applicable;
- operational state where applicable;
- criticality metadata where available;
- completeness status where supported;
- open knowledge-gap count where supported;
- source where available;
- updated timestamp where available.

At minimum, graph edges should expose:

- namespaced key;
- edge family;
- underlying edge UUID;
- source key;
- target key;
- relationship type key where applicable;
- relationship type name where applicable;
- API-provided display label;
- required_for_operation where supported;
- valid_from where supported;
- valid_to where supported;
- source where available;
- knowledge state, initially accepted.

The graph response should expose:

- focus key;
- effective as_of timestamp;
- requested depth;
- truncation state;
- safe warnings;
- nodes;
- edges.

Do not add a global numeric confidence value in C2.1.

Completeness, gap count, source, and freshness metadata may be returned as
qualifiers, but they must not be combined into an undocumented confidence score.

Do not fabricate completeness for Business Functions if a Business Function
completeness evaluator does not yet exist.

----------------------------------------------------------------------
6. GENERIC API
----------------------------------------------------------------------

Add a generic focused graph endpoint equivalent to:

GET /api/operational-graph

Support these initial parameters:

- focus_type: asset | service | business_function
- focus_id: UUID
- max_depth: default 1, allowed range 0 through 2
- direction: both | outgoing | incoming, default both
- as_of: optional timestamp, default request time
- node_limit: default 250, hard maximum 500
- edge_family: optional filter using the repository's normal query conventions

Follow established API validation and error-handling conventions.

Authorization expectations:

- Asset focus requires the existing Asset view permission.
- Service focus requires the existing Service view permission.
- Service dependency expansion must respect the existing dependency permission
  model.
- Business Function focus requires the existing Business Function view
  permission.
- Every node and both endpoints of every edge must be independently viewable.
- Omit the complete edge when either endpoint is inaccessible.
- Never return a dangling edge.
- Never expose an inaccessible entity's ID, name, type, or existence.
- Never expose hidden-node counts through warnings, truncation totals, or
  response metadata.
- Preserve the repository's current non-disclosing behavior for missing versus
  inaccessible records.

----------------------------------------------------------------------
7. SOURCE MAPPING
----------------------------------------------------------------------

Project the existing accepted records through one graph interface.

Asset node:

- Source: Asset.
- Include only when authorized and viewable.

Service node:

- Source: Service.
- Follow the documented default handling for archived Services.

Business Function node:

- Source: BusinessFunction.
- Follow the documented default handling for inactive Business Functions.

Asset-to-Asset edge:

- Source: AssetRelationship.
- Resolve labels through managed RelationshipType data.
- Preserve the stored source and target direction.
- Do not invent historical validity where the current model has none.

Service-to-Asset edge:

- Source: ServiceAssetDependency.
- Apply the established temporal active-at-as_of rule.
- Carry required_for_operation without interpreting impact.

Service-to-Service edge:

- Source: ServiceDependency.
- Apply temporal filtering.
- Preserve incoming and outgoing direction.
- Preserve legitimate cycles.

Service-to-Business-Function edge:

- Source: ServiceBusinessFunction.
- Apply temporal filtering.
- Preserve direction from Service to Business Function even when the Business
  Function is the visual focus.

Completeness and gaps:

- Load supported summaries and active gap counts in bounded batches.
- Avoid one metadata query per graph node.
- Apply all authorization and scope restrictions.

Relationship labels:

- Supply semantic labels from the API.
- Do not require the frontend to infer labels from hard-coded keys.

----------------------------------------------------------------------
8. PROJECTION ALGORITHM
----------------------------------------------------------------------

Use a bounded, deterministic, cycle-safe breadth-first structural expansion.

Expected behavior:

1. Resolve and authorize the focus.
2. Add the focus node.
3. Queue the focus at depth zero.
4. Expand the permitted edge families for the current frontier.
5. Resolve both endpoints.
6. Omit the complete edge silently when either endpoint is inaccessible.
7. Add authorized nodes and legitimate edges using namespaced keys.
8. Queue newly discovered endpoints until max_depth is reached.
9. Track visited nodes to prevent repeated expansion.
10. Do not discard a legitimate edge merely because both endpoint nodes already
    exist.
11. Apply the node limit deterministically.
12. Never return an edge whose endpoint is absent.
13. Sort nodes and edges by stable keys before returning.
14. Return an explicit truncation state and safe warning when limits are reached.

Direction filtering must use semantic source and target direction, not visual
layout direction.

----------------------------------------------------------------------
9. EXISTING ROUTE COMPATIBILITY
----------------------------------------------------------------------

Preserve these endpoints and their existing public contracts:

- GET /api/services/{service_id}/graph
- GET /api/business-functions/{function_id}/graph

Refactor their graph assembly to use the shared operational graph builder.

Recommended sequence:

1. Implement graph identity and shared schemas.
2. Implement source loaders and builder.
3. Implement the generic route.
4. Add compatibility adapters from the new graph result to existing response
   shapes.
5. Refactor the Service graph route to use the builder and adapter.
6. Refactor the Business Function graph route to use the builder and adapter.
7. Keep existing frontend callers working.
8. Do not remove or deprecate the old contracts in C2.1.

Do not copy the old graph logic into another service. Extract and consolidate it.

----------------------------------------------------------------------
10. WEB FOUNDATION
----------------------------------------------------------------------

Add shared presentation-neutral graph utilities following existing web
conventions.

Possible responsibilities:

- normalize nodes and edges using namespaced keys;
- preserve source and target direction;
- render API-provided labels;
- use API-provided href values;
- expose truncation visibly;
- distinguish unknown or not-evaluated metadata;
- support keyboard access;
- support responsive layouts.

A reasonable shape may include:

- apps/web/lib/operational-graph.mjs
- apps/web/components/operational-graph-view.js
- corresponding web tests

Adapt this to the existing web structure.

Do not redesign the Homepage, Service Operations, Impact Analysis, or Change
Simulation screens in this task.

Do not add a large graph-rendering dependency unless the existing implementation
cannot provide a maintainable focused graph view and the dependency is justified.

The web layer must not calculate:

- impact;
- recovery readiness;
- confidence;
- severity;
- outage propagation;
- business criticality conclusions.

----------------------------------------------------------------------
11. TEST REQUIREMENTS
----------------------------------------------------------------------

Use the detailed test plan in:

docs/testing/release-c2-operational-graph.md

Add or update automated tests covering at least:

Graph identity:

- namespaced node keys;
- namespaced edge keys;
- no collision between entity tables.

Focus behavior:

- Asset focus;
- Service focus;
- Business Function focus;
- depth zero;
- depth one;
- depth two.

Direction:

- incoming;
- outgoing;
- both;
- semantic direction remains unchanged.

Temporal behavior:

- before valid_from;
- at valid_from;
- between boundaries;
- valid_to boundary using the repository's documented convention;
- after valid_to;
- no valid_to;
- default request-time behavior.

Cycles and deduplication:

- Service cycles terminate;
- Asset cycles terminate;
- legitimate cyclic edges remain;
- nodes are not duplicated;
- edges are not duplicated;
- multiple legitimate paths remain represented.

Limits:

- no truncation below limit;
- explicit truncation above limit;
- deterministic truncation;
- hard maximum validation;
- no dangling edges;
- inaccessible nodes excluded before limit and warning calculations.

Authorization and IDOR:

- cross-customer focus substitution;
- cross-site focus substitution;
- workspace context does not broaden access;
- mixed entity permissions;
- hidden adjacent endpoints;
- no hidden labels, IDs, counts, or warnings;
- global authorized access;
- Viewer read-only behavior;
- grandfathered cross-context Asset relationship behavior where applicable.

Accepted knowledge:

- unaccepted discovery relationships excluded;
- accepted reconciliation reflected;
- rejected or deferred reconciliation not reflected;
- conflicting source-current assertion does not override accepted knowledge;
- manual accepted edits reflected;
- ended temporal dependencies excluded from current projection.

Completeness and provenance:

- Asset completeness correctly mapped;
- Service completeness correctly mapped;
- no fabricated Business Function completeness;
- gap counts scoped correctly;
- evaluator failure is not reported as complete;
- no undocumented global confidence score.

Compatibility:

- current Service graph response remains compatible;
- current Business Function graph response remains compatible;
- existing Service and Business Function pages still render.

Performance:

- prevent obvious N+1 query behavior;
- batch RelationshipType loading;
- batch completeness and gap loading;
- test a representative default-limit graph;
- test hard-limit behavior;
- do not add caching to conceal inefficient queries.

Web:

- namespaced keys;
- API-provided labels and hrefs;
- truncation display;
- accessible empty states;
- no client-side impact or confidence invention;
- current graph pages regression-covered.

----------------------------------------------------------------------
12. MIGRATIONS AND DATA SAFETY
----------------------------------------------------------------------

C2.1 is expected not to require a database migration.

Confirm:

- Alembic remains at a single head.
- Existing databases start without reset or destructive backfill.
- Seed and startup behavior remain idempotent.
- No graph table is introduced.
- No external graph service is introduced.
- No browser-visible secret is added.

Before creating any migration, stop and explain precisely why C2.1 cannot be
implemented using the current data model.

Do not reset, delete, or regenerate existing customer data.

----------------------------------------------------------------------
13. VALIDATION
----------------------------------------------------------------------

Determine and run the repository-standard commands for:

- API tests;
- graph-specific API tests;
- security and IDOR tests;
- web tests;
- web production build;
- migration/Alembic validation;
- plugin tests where relevant;
- Docker/PostgreSQL acceptance where available and practical.

Also run formatting, linting, and type-checking commands where they are already
part of the repository.

Do not claim a test passed unless it was actually run.

When a test cannot be run, record:

- the exact test not run;
- why it was not run;
- what remains unverified.

Do not weaken an existing test merely to make the implementation pass.

----------------------------------------------------------------------
14. DOCUMENTATION AND RELEASE EVIDENCE
----------------------------------------------------------------------

After implementation and validation:

1. Update docs/product/release-c2-plan.md with actual implementation notes.
2. Update docs/architecture/operational-graph.md if implementation details
   differ.
3. Update docs/testing/release-c2-operational-graph.md with confirmed commands or
   decisions.
4. Re-audit docs/product/feature-ledger.md against the completed working tree or
   named commit.
5. Preserve the historical 09d2271 audit evidence; add a new audit point rather
   than silently rewriting historical results.
6. Record:
   - implementation status;
   - relevant commit hash if a commit was created;
   - migration head;
   - exact API test result;
   - exact web test result;
   - production build result;
   - plugin test result if run;
   - Docker/PostgreSQL result if run;
   - known limitations;
   - unexecuted checks.
7. Do not mark C2.2, C2.3, Impact Analysis, Change Simulation, Recovery, B2 live
   discovery, F1 Documents, Interface-first IP cleanup, or legacy Service Asset
   conversion as implemented.
8. Do not claim tests or acceptance checks that were not performed.

Update roadmap status only to the level supported by implementation evidence.

----------------------------------------------------------------------
15. WORKING METHOD
----------------------------------------------------------------------

Implement the work in small, reviewable increments.

Suggested logical sequence:

- C2.1-01: confirm documentation and existing implementation baseline
- C2.1-02: graph identity helpers and schemas
- C2.1-03: source loaders
- C2.1-04: shared builder
- C2.1-05: generic API route
- C2.1-06: authorization and IDOR coverage
- C2.1-07: Service graph compatibility adapter
- C2.1-08: Business Function graph compatibility adapter
- C2.1-09: shared web normalization and view foundation
- C2.1-10: regression and performance validation
- C2.1-11: documentation and ledger update

Keep the working tree buildable throughout.

Follow the repository's established naming, formatting, testing, and
error-handling conventions.

Avoid broad refactoring unrelated to the operational graph.

Do not commit generated files, build output, local databases, environment files,
credentials, or secrets.

Before completion, confirm that the C2.1 change set contains none of the
following unless required solely for compatibility and explicitly justified:

- Integration management or worker orchestration;
- live Proxmox execution;
- Documents product surfaces;
- Interface-first IP redesign;
- legacy Service Asset conversion;
- C2.2 dependency semantics;
- C2.3 analysis conclusions.

Do not push or merge.

----------------------------------------------------------------------
16. COMPLETION REPORT
----------------------------------------------------------------------

At completion, provide:

1. Summary of the implemented architecture.
2. Current branch, commit state, and migration head.
3. Material differences from the 09d2271 feature-ledger baseline.
4. Files added and changed.
5. Generic API contract and examples.
6. How authorization and non-disclosure are enforced.
7. How temporal filtering, cycles, depth, and truncation work.
8. How existing Service and Business Function graph contracts were preserved.
9. Tests and validation commands actually run.
10. Exact results of those checks.
11. Known limitations and deferred C2.2/C2.3 work.
12. Confirmation that B2, F1, Interface-first IP, and legacy Service Asset work
    remained outside scope.
13. Documentation updates completed.
14. Suggested logical Git commit messages.
15. Any manual verification steps I should perform before merging.

The task is complete only when the shared graph foundation, compatibility
adapters, tests, and repository documentation are all implemented to the extent
supported by the current codebase.
```
