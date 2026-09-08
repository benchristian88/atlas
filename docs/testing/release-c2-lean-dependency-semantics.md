# Release C2.2 Lean Dependency Semantics test plan

Status: implemented on the C2.2 feature working tree; subsequent live LXC
acceptance complete

Base commit: `bd2ab6cacf7b6f11acad188827744f6105e50310`

## Working-tree validation — 8 September 2026

Executed results:

- `cd apps/api && .venv/bin/pytest -q tests/test_dependency_semantics.py` —
  **13 passed**, 480 warnings;
- `cd apps/api && .venv/bin/pytest -q tests/test_operational_graph.py` —
  **16 passed**, 480 warnings;
- `cd apps/api && .venv/bin/pytest -q` — **187 passed**, 480 warnings;
- `cd apps/web && npm test` — **76 passed**;
- `cd apps/web && npm run build` — **passed**, 33 pages generated;
- `apps/api/.venv/bin/python -m pytest -q plugins/sdk` — **5 passed**;
- `PYTHONPATH=plugins/sdk:plugins/proxmox apps/api/.venv/bin/python -m pytest -q plugins/proxmox/tests` — **22 passed**;
- `cd apps/api && .venv/bin/python -m compileall -q app tests` — **passed**;
- `cd apps/api && .venv/bin/alembic heads` — one head,
  `20260908_0014`;
- `cd apps/api && .venv/bin/alembic upgrade head --sql` — **passed**; and
- disposable PostgreSQL 17 C2.1→C2.2 upgrade, persistence, graph,
  downgrade, and re-upgrade checks — **passed**; and
- `git diff --check` — **passed**.

Docker was unavailable. This did not block migration validation because the
installed PostgreSQL server was run against a disposable data directory, then
stopped and removed.

## Subsequent live LXC acceptance

After the implementation-time validation above, C2.2 completed live manual
acceptance in the deployed test LXC against its PostgreSQL-backed Atlas
environment. This acceptance verified:

- upgrading the real C2.1-backed environment preserved the existing Reverse
  Proxy → DNS Service and DNS Service → Adguard Home Asset dependencies,
  without duplicate dependency rows or fabricated dependency groups;
- an existing ungrouped Service→Service dependency could be changed between
  Required and Optional, with the selected value surviving save and reload and
  remaining consistent with `required_for_operation`;
- an Optional, All required, Service degraded dependency behaviour containing
  DNS Resolution and Filtering persisted after save and reload;
- removing that behaviour retained the underlying Reverse Proxy → DNS
  dependency as Optional, removed the group metadata, and restored the explicit
  Unknown failure effect for the ungrouped dependency;
- a real mixed dependency behaviour named `Core Operation` persisted with
  Required, All required, and Service unavailable semantics across the Nginx
  Proxy Manager Service→Asset dependency and the DNS Resolution and Filtering
  Service→Service dependency, with both members showing the same behaviour in
  the Service UI;
- the generic Operational Graph projected both mixed dependency edges with the
  same group identity and `dependency_strategy = all`,
  `dependency_requirement = required`, `failure_effect = unavailable`, and
  `required_for_operation = true`, without changing canonical edge direction;
- incoming Service→Service traversal from DNS Resolution and Filtering still
  returned Reverse Proxy and Application Publishing → Depends on → DNS
  Resolution and Filtering, preserving canonical source/target direction and
  the `Core Operation` semantics; and
- for a principal in another tenant,
  `GET /api/services/{service_id}/dependency-groups` returned the normal
  non-disclosing `{"detail":"Record not found"}` response without exposing
  dependency-semantic information.

The `any` / “Any one is sufficient” strategy was not manually exercised in the
live LXC because the real topology had only one AdGuard provider and no genuine
redundant pair. Automated C2.2 coverage exercises `any`; no fake topology was
created solely for manual acceptance. This bounded manual coverage does not
block C2.2 completion.

These live results are subsequent acceptance evidence. They do not replace or
alter the implementation-time automated counts, PostgreSQL 17 fixture results,
or Docker limitation recorded above.

## Scope

C2.2 stores and exposes only:

- dependency requirement: `required` or `optional`;
- dependency-set strategy: `all` or `any`; and
- unsatisfied-set effect: `unavailable`, `degraded`, or `unknown`.

It does not evaluate availability, propagate failure, calculate blast radius,
or return an impact result. Existing Service→Asset and Service→Service rows
remain the authoritative relationships.

## Automated coverage

Focused API coverage verifies:

- the closed lean vocabulary and explicit unknown state;
- temporal group and membership schema constraints;
- unchanged ungrouped required/optional compatibility;
- `all` and `any` group representation;
- Service→Asset, Service→Service, and mixed membership;
- ended membership exclusion;
- non-disclosing rejection of a dependency owned by another Service;
- additive route registration and migration shape; and
- generic Operational Graph semantic metadata without consequence analysis.

Existing C2.1 tests continue to cover direction, depth, cycles, deterministic
ordering, temporal edges, authorization boundaries, non-disclosure, limits, and
compatibility adapters. Web tests cover plain wording, explicit Unknown,
required/optional fallback, permission-gated editing, and use of the normal
Service workflow.

Supported commands:

```bash
cd apps/api
.venv/bin/pytest -q tests/test_dependency_semantics.py
.venv/bin/pytest -q tests/test_operational_graph.py
.venv/bin/pytest -q
.venv/bin/alembic heads
.venv/bin/alembic upgrade head --sql

cd ../web
npm test
npm run build

cd ../..
apps/api/.venv/bin/python -m pytest -q plugins/sdk
PYTHONPATH=plugins/sdk:plugins/proxmox apps/api/.venv/bin/python -m pytest -q plugins/proxmox/tests
git diff --check
```

## PostgreSQL migration validation

A disposable PostgreSQL 17 database should be migrated to C2.1 head
`20260720_0013`, populated with representative required and optional
dependencies, and upgraded to `20260908_0014`.

Verify that:

1. both dependency rows and their original `required_for_operation` values are
   unchanged immediately after upgrade;
2. zero dependency groups exist until a user explicitly creates one;
3. a mixed group can include a Service→Asset and outgoing Service→Service row;
4. changing group semantics creates a new group version, ends old memberships,
   and synchronizes the compatibility required flag;
5. the generic Operational Graph exposes only the active group version;
6. ending a group leaves both dependency relationships in place; and
7. downgrade to C2.1 and re-upgrade to C2.2 preserve the dependencies.

## Authorization acceptance

- A Viewer with `services.view` and `service_dependencies.view` can see semantic
  labels but receives no editing controls.
- A user needs `service_dependencies.manage` in the subject Service scope for
  every group mutation.
- A supplied membership ID must resolve to a current dependency owned by the
  subject Service. Another Service's dependency returns the normal
  non-disclosing not-found response.
- The dependency and group customer/site scope must match; semantic metadata is
  omitted from graph edges if persisted data violates that invariant.
- An inaccessible focus or endpoint remains subject to C2.1 endpoint filtering;
  group names and IDs must not create a side channel.

## Manual test-LXC acceptance checklist

Use existing real topology where possible:

1. Upgrade the test LXC and confirm the existing “Reverse Proxy and Application
   Publishing depends on DNS Resolution and Filtering” relationship and
   “DNS Resolution and Filtering provided by Adguard Home” relationship still
   render.
2. On the DNS Service, change one ungrouped dependency between Required and
   Optional and reload the page. Confirm the label and legacy required flag
   agree.
3. Create a single-member dependency behaviour and exercise Service
   unavailable, Service degraded, and Unknown.
4. Create an “all” set from genuine dependencies that jointly provide one need.
5. Where two genuine provider dependencies exist, create an “any” set and
   confirm the UI says “Any one is sufficient”. Do not fabricate topology only
   for this manual check; automated coverage handles the case otherwise.
6. Call `GET /api/operational-graph` focused on the Service and confirm
   `dependency_group_id`, group name, strategy, requirement, failure effect,
   and the unchanged `required_for_operation` field appear on applicable edges.
7. Repeat existing incoming/outgoing traversal checks and confirm canonical
   source/target direction is unchanged.
8. As another tenant or site-only principal, substitute the Service and group
   IDs and confirm normal non-disclosing not-found behavior with no semantic
   names or counts returned.

## Deferred checks

No C2.2 test should expect minimum/quorum, weighted or conditional rules,
confidence scoring, failure propagation, C2.3 consequence results, or the C2.4
visual redesign.
