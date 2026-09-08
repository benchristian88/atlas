# Release C2.1 Operational Graph test plan

Status: C2.1 merged; automated coverage and subsequent live acceptance complete

C2.2 additively extends applicable generic graph edges with stored dependency
semantics while preserving every C2.1 structural contract in this plan. See
[`release-c2-lean-dependency-semantics.md`](release-c2-lean-dependency-semantics.md)
for the semantic and migration checks.

This document preserves the Release C2.1 validation contract and records the
checks executed against the feature working tree before its merge to `dev`.

## Working-tree validation — 3 September 2026

Base commit: `f693f492deb0d3b317134c407e0897c9e1b25d58`

Delivery commit: `a9f41df`; merged to `dev` by `1842d16`. The merge has the
same tree as the delivery commit.

Executed results:

- `cd apps/api && .venv/bin/pytest -q` — **174 passed**, 468 deprecation
  warnings;
- `cd apps/api && .venv/bin/pytest -q tests/test_operational_graph.py` —
  **16 passed**, 468 deprecation warnings;
- `cd apps/web && npm test` — **74 passed**;
- `cd apps/web && npm run build` — **passed**, 33 pages generated;
- `apps/api/.venv/bin/python -m pytest -q plugins/sdk` — **5 passed**;
- `apps/api/.venv/bin/python -m pytest -q plugins/proxmox/tests` — **22 passed**;
- `cd apps/api && .venv/bin/alembic heads` — one head,
  `20260720_0013`; and
- `git diff --check` — passed at the implementation checkpoint.

`alembic current` could not run because no PostgreSQL server was listening on
localhost. Docker/PostgreSQL acceptance could not run because the environment
did not provide the `docker` executable. This records the limitation at the
original working-tree audit point; no migration was added by C2.1.

## Subsequent live pre-merge acceptance — 3 September 2026

After the working-tree audit, C2.1 completed live manual acceptance in the
deployed test LXC against its real PostgreSQL-backed Atlas environment. The
manual acceptance covered:

- generic graph behavior with Asset, Service, and Business Function focus;
- depth `0`, `1`, and `2` behavior;
- incoming and outgoing traversal;
- edge-family filtering;
- safe node-limit truncation with no dangling edges;
- Service→Service dependency traversal in both directions;
- preservation of canonical semantic edge direction during reverse traversal;
- cross-tenant focus non-disclosure returning the normal “Record not found”
  response; and
- final migration and repository checks completed before merge.

This subsequent acceptance closes the live PostgreSQL/deployed-environment
release check that was unavailable during the original audit. It does not alter
or replace the automated counts and environment limitations recorded above.

## C2.2 live regression acceptance

Subsequent C2.2 acceptance in the same deployed PostgreSQL-backed test LXC
reconfirmed canonical Service→Service edge direction, incoming traversal, and
generic graph compatibility while projecting the additive `Core Operation`
dependency semantics. A principal in another tenant also received the normal
non-disclosing not-found response from the dependency-groups route. This is a
small C2.1 regression record, not a rewrite of the historical C2.1 acceptance
above; full C2.2 evidence is recorded in
[`release-c2-lean-dependency-semantics.md`](release-c2-lean-dependency-semantics.md).

C2.1 is implemented and merged. The reference fixture is deliberately created
with current manual UI/API capabilities. This plan does not test
Integration CRUD, secrets, worker dispatch, live Proxmox execution, Documents
UI, Interface-first IP cleanup, or legacy Service Asset conversion.

## Purpose

C2.1 introduces a shared API-owned graph projection over accepted Assets,
Services, Business Functions, and their current relationships. Testing must prove
both graph correctness and preservation of the existing Atlas authorization,
knowledge, and compatibility boundaries.

Read alongside:

- [`../product/feature-ledger.md`](../product/feature-ledger.md)
- [`../product/release-c2-plan.md`](../product/release-c2-plan.md)
- [`../architecture/operational-graph.md`](../architecture/operational-graph.md)
- [`../decisions/0001-shared-operational-graph.md`](../decisions/0001-shared-operational-graph.md)
- [`security-and-access-test-plan.md`](security-and-access-test-plan.md)
- [`homelab-service-mvp.md`](homelab-service-mvp.md)

## Supported validation commands

Run only the checks supported by the repository at the implementation commit and
do not report a command as passing unless it completed.

```bash
cd apps/api
pip install -r requirements-dev.txt
pytest
alembic current
alembic heads

cd ../web
npm install
npm test
npm run build

cd ../..
python3 -m pytest plugins/sdk
PYTHONPATH=plugins/sdk:plugins/proxmox python3 -m pytest plugins/proxmox/tests
```

Where Docker and PostgreSQL are available, also run the documented Compose and
migration acceptance flow against a disposable copy of representative data.

## Representative homelab fixture

Create or seed a fixture that reflects the planned product concepts without
assuming their future workflows exist.

### Infrastructure Assets

- UDM Pro or Internet gateway;
- USW-Aggregation switch;
- PVE1, PVE2, and PVE3 hosts;
- Synology NAS;
- PBS backup server;
- Immich LXC;
- Immich application Asset;
- Grafana LXC;
- Atlas LXC;
- Authentik or another identity workload; and
- one unrelated Asset in the same site.

### Services

- Photo Management;
- Monitoring;
- Infrastructure Knowledge;
- Authentication or Single Sign-On; and
- DNS or Home Connectivity.

### Business Functions

- Household Information;
- Monitoring and Administration; and
- Secure Access or Home Connectivity.

### Relationships

Include all supported edge families:

- Asset-to-Asset physical/platform/dependency relationships;
- Service-to-Asset dependencies;
- Service-to-Service dependencies;
- Service-to-Business Function links; and
- a legitimate two-Service cycle.

Give at least one Service multiple upstream dependencies and at least one
Service multiple downstream dependants. Include one isolated entity. Ensure the
Application Asset is linked to its host and to the first-class Service that it
supports without treating those two entity kinds as interchangeable.

Create a second customer and a second site with similarly named records so
scope and ID substitution cannot pass accidentally through name-based logic.
Include a customer-wide Service and a Site-scoped Service to exercise the
existing compatible-scope rules.

## Contract tests

| Case | Required assertion |
| --- | --- |
| Namespaced node identity | Node keys contain entity type and UUID; identical UUID values in different entity tables remain distinct |
| Namespaced edge identity | Edge keys contain family and UUID; families cannot collide |
| Focus metadata | Response identifies requested focus, captured generation time, depth, and truncation state |
| Node contract | Only documented bounded fields are returned; secrets, raw evidence, and unbounded notes are absent |
| Edge contract | Source and target keys, family, relationship metadata, required flag, temporal values, and accepted knowledge state serialize correctly |
| Deterministic ordering | Repeated requests against unchanged data return nodes and edges in the same order |
| Empty projection | A viewable isolated focus returns one node, no edges, and no false error |
| Invalid query | Unsupported focus type, direction, depth, family, or limit returns safe validation errors |

## Source mapping tests

### Asset nodes and relationships

- A focused Asset includes authorized adjacent Asset relationships.
- Managed Relationship Type labels are returned where available.
- Stored source/target direction is preserved.
- An inactive managed type remains readable on an existing edge where current
  repository lifecycle rules allow it.
- A missing type lookup uses the documented safe fallback without changing edge
  direction.

### Service nodes and Asset dependencies

- A focused Service includes active Service-to-Asset dependencies.
- `required_for_operation` is carried without being interpreted as an outage
  conclusion.
- Archived Services follow the documented default behavior.
- An ended dependency is absent from a current projection.

### Service-to-Service dependencies

- Incoming and outgoing links are distinguishable by source/target.
- A two-Service cycle returns both valid edges and terminates.
- A self-dependency remains rejected by the existing mutation path.
- A current projection excludes ended links.

### Business Functions

- A focused Business Function includes its supporting Services and permitted
  Service dependencies within the requested depth.
- An inactive Business Function follows the documented default behavior.
- Service-to-Business Function direction remains Service to Function even when
  the Function is the visual focus.

## Temporal tests

Freeze the captured request time and use explicit UTC timestamps around each
boundary. C2.1 has no caller-selected historical query.

| Case | Required assertion |
| --- | --- |
| Before `valid_from` | Temporal edge is absent |
| At `valid_from` | Behavior matches the documented inclusive boundary |
| Between boundaries | Edge is present |
| At `valid_to` | Behavior matches the documented exclusive/inclusive choice consistently |
| After `valid_to` | Edge is absent |
| No `valid_to` | Edge remains present after `valid_from` |
| Current-only Asset relationship | Response does not claim historical reconstruction |
| Captured request time | Response records the effective request time and current links are stable under a frozen clock |
| Historical query | No caller-selected `as_of` parameter is exposed in C2.1 |

## Projection-depth and cycle tests

- Depth `0` returns the focus node only.
- Depth `1` returns direct authorized neighbors and their edges.
- Depth `2` returns the next structural frontier but no deeper nodes.
- Direction `outgoing`, `incoming`, and `both` apply to semantic edge direction.
- Reverse traversal never swaps serialized source/target or changes the
  relationship's canonical meaning.
- A Service cycle does not cause repeated expansion.
- An Asset cycle or bidirectional pair does not duplicate nodes or edges.
- An edge between two already visited nodes is retained once.
- Multiple paths to the same node retain distinct legitimate edges.

## Limit and truncation tests

- A result below the node limit reports `truncated=false`.
- A result exceeding the limit reports `truncated=true` and a safe warning.
- Truncation is deterministic across repeated requests.
- No edge is returned with a missing endpoint.
- Inaccessible nodes are filtered before truncation totals or warnings are
  calculated.
- A caller cannot infer hidden-node count by comparing limit behavior across
  scopes.
- Hard maximum validation prevents an unbounded request.

## Authorization and IDOR isolation

These cases supplement the existing security test plan.

### Focus substitution

- A Customer A principal cannot focus an Asset, Service, or Business Function
  belonging only to Customer B.
- A Site A1 assignment cannot focus Site A2 records by path/query ID.
- A selected workspace context does not broaden permission.
- A global user can focus authorized records across contexts as expected.

### Expansion non-disclosure

- An authorized focus with an inaccessible adjacent endpoint omits the complete
  edge and endpoint.
- The response contains no dangling source/target key.
- Warnings do not mention the hidden entity, type, name, or count.
- The same rule applies to Asset, Service, and Business Function endpoints.
- A mixed-permission caller receives only the subgraph for entity types and
  scopes they can view.

### Legacy cross-context Asset relationship

Where the repository retains a grandfathered cross-context edge:

- it appears only when both endpoint contexts are authorized;
- it is absent when only one endpoint is authorized;
- the graph does not reveal the other endpoint through counts or warnings; and
- C2.1 does not permit creation or mutation of another cross-context edge.

### Viewer behavior

- A Viewer with appropriate view permissions can read the graph in scope.
- The graph route has no mutation side effects.
- Viewer access does not expose assertions, evidence, notes, or administrative
  metadata beyond the documented graph contract.

## Accepted-knowledge tests

- A discovered but unaccepted proposed relationship does not appear as an
  operational graph edge.
- Accepting reconciliation updates the operational record and makes the edge
  eligible for the graph.
- Rejecting or deferring a proposal leaves the operational graph unchanged.
- A source-current conflicting assertion does not replace the accepted node
  value.
- A manual accepted edit updates graph display metadata.
- Retraction or ending of an accepted temporal dependency removes it from the
  current graph while history remains available through existing lifecycle APIs.

## Completeness and provenance metadata tests

Where C2.1 includes these qualifiers:

- Asset completeness maps to the correct Asset node.
- Service completeness maps to the correct Service node.
- No Business Function completeness is fabricated before that evaluator exists.
- Open gap counts are scoped and exclude inaccessible gaps.
- An evaluator failure reports `not_evaluated`, not false completeness.
- Source and updated timestamps match the operational record or documented
  summary source.
- No global numeric confidence value is returned unless separately designed and
  tested.

## Existing route compatibility

### Service graph

For a representative C1 Service fixture, compare the pre-refactor contract with
the adapter output:

- selected Service present;
- supporting Assets present;
- permitted adjacent Asset relationships present according to current behavior;
- incoming and outgoing connected Services present;
- Business Functions present;
- labels, directions, IDs, hrefs, and edge families remain compatible; and
- unauthorized endpoints remain absent.

### Business Function graph

Verify the current route still returns:

- selected Business Function;
- supporting Services;
- permitted Service Asset dependencies;
- current labels and hrefs; and
- no unexpected deeper recursion.

Frontend Service and Business Function pages must continue to render without
requiring the new generic contract during the compatibility stage.

## Generic API tests

- Asset focus returns the documented structural projection.
- Service focus returns the documented structural projection.
- Business Function focus returns the documented structural projection.
- Edge-family filtering is applied after authorization.
- Direction filtering uses semantic direction.
- Unsupported focus/edge combinations return a safe empty result or documented
  validation response.
- No request writes, commits, audits a mutation, or changes accepted knowledge.

## Query and performance regression

The exact target should be recorded after implementation profiling, but C2.1
must prevent obvious N+1 behavior.

Required checks:

- query count does not increase linearly by one or more metadata queries per
  returned node;
- Relationship Types are loaded in bounded queries;
- completeness summaries/gap counts are loaded in batches;
- the 250-node default fixture completes within an agreed local test threshold;
- a 500-node hard-limit fixture returns deterministically without excessive
  memory growth; and
- performance changes do not weaken authorization filtering.

Do not add a cache to make an inefficient or unsafe implementation pass.

## Web tests

- graph identity uses namespaced keys;
- API-provided labels are rendered;
- source/target semantic direction remains available to the view;
- links use API-provided `href` values;
- isolated and empty states are readable;
- truncation warning is visible and accessible;
- unknown or not-evaluated metadata is not shown as healthy or complete;
- keyboard focus and responsive layout remain usable;
- no client calculation invents impact, confidence, or recovery status; and
- Service and Business Function current pages remain regression-covered.

## Migration and deployment validation

C2.1 is expected to require no graph persistence migration. Confirm:

- `alembic heads` remains a single head;
- existing data starts without reset or backfill loss;
- repeated startup and seeding remain idempotent;
- no graph table or external graph service is introduced accidentally;
- Docker Compose configuration does not add browser-visible secrets; and
- current deployment documentation remains accurate.

If implementation adds a migration for an unrelated necessity, test it against
both empty and representative existing databases and document the reason.

## Regression areas

After C2.1, manually and automatically verify that these existing areas still
work:

- login, forced password change, profile, and logout;
- customer/site selector and scope;
- Assets, interfaces, networks, and relationships;
- Knowledge Graph topology lenses;
- Discovery simulation and run history;
- Reconciliation;
- Changes and Asset fact history;
- Knowledge Gaps and completeness;
- Services and Service dependency editing;
- Business Functions;
- administration and reference data;
- current generated-document behavior; and
- plugin SDK and Proxmox contracts.

## Release evidence

The C2.1 release record distinguishes the original automated audit evidence
from the subsequent live pre-merge acceptance. It records:

- delivered commit hash;
- migration head;
- exact API test result;
- exact web test result;
- web production build result;
- plugin test results if run;
- subsequent deployed PostgreSQL acceptance;
- known limitations; and
- any unexecuted check.

Then update [`../product/feature-ledger.md`](../product/feature-ledger.md) through a
new repository audit rather than copying the roadmap acceptance criteria into
the ledger.
