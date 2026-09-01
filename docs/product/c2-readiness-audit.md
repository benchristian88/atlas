# Release C2.1 readiness audit

## Baseline

| Item | Audited value |
| --- | --- |
| Branch | `dev` |
| Commit | `4b0bfac6c746c56df9e1bfe16bae33d8dff3721e` |
| Commit description | Merge PR #6, `docs/feature-ledger-updates` |
| Working tree at audit start | Clean |
| Migration heads | One |
| Migration head | `20260720_0013` (`homelab_service_mvp`) |
| Validation date | 30 August 2026 (Pacific/Auckland) |
| Repository-local `AGENTS.md` | None present at the audited commit; added later in `534b489` |

The repository contains 257 tracked files. Its runtime baseline is FastAPI
0.116.1, SQLAlchemy 2.0.43, Alembic 1.16.4, PostgreSQL 17, Redis 7, Python 3.12
container images, Next.js 16.2.10, React 19.1.1, and Atlas web/plugin package
versions 0.1.0. The worker has no independent package version.

The two supplied reviews were originally read from Codex attachment copies
because macOS did not expose the original Desktop paths to the workspace
process:

- `Atlas Product Feature Status Review` (transcript-derived, 24 July 2026);
- `Atlas Product Feature Status Review — Repository-Reconciled Edition`
  (repository audit at `09d2271`).

Repository copies were subsequently added at:

- [`../history/product-reviews/atlas-product-feature-status-review.md`](../history/product-reviews/atlas-product-feature-status-review.md); and
- [`../history/product-reviews/atlas-product-feature-status-review-reconciled.md`](../history/product-reviews/atlas-product-feature-status-review-reconciled.md).

Their dated baselines and location under `docs/history/product-reviews/` identify
them as historical, non-canonical evidence. They do not replace current code,
accepted ADRs, architecture, the roadmap, or this readiness audit.

## Delta reconciliation — 2 September 2026

The previous audit work was committed as `cab11e4` (`docs:align roadmap`). At
the start of this delta review, the committed tree differed from that commit
only by `534b489`, which adds the root `AGENTS.md`; the two historical reviews
were newly present in the working tree under the archive path above. No
application code, schema, migration, API, or UI implementation changed after
the previous audit.

The root instructions and both repository copies of the historical reviews were
read in full. The root instructions confirm the previous audit's source-of-truth
order, manual-first sequencing, B2/C2.1 separation, domain boundaries,
authorization requirements, PostgreSQL projection architecture, and strict
C2.1/Impact Analysis boundary. The historical reviews confirm the component
findings already reconciled below. Their July recommendation to complete the
operational Proxmox journey before C2 and their classification of structural
graph foundations as partial Impact Analysis remain superseded historical
conclusions; they do not change current implementation status or release
sequencing.

No Feature Ledger classification, C2.1 prerequisite, or readiness conclusion
changed in this delta review. The **GO** conclusion remains valid.

## Current implemented foundation

C2.1 can rely on:

- PostgreSQL-backed customer/site-scoped Assets, interfaces, Networks, and
  Asset relationships;
- managed Asset and Relationship Types, including endpoint-kind
  applicability;
- first-class Services and Business Functions;
- temporal Service-to-Asset, Service-to-Service, and
  Service-to-Business-Function links;
- legitimate Service cycles and non-destructive link ending;
- accepted-versus-source-current assertions, evidence, reconciliation, and
  manual declarations;
- Asset and Service completeness summaries and Knowledge Gaps;
- focused Service and Business Function graph response contracts;
- Knowledge Graph topology lenses over current Asset knowledge;
- API-owned permissions and global/customer/site scope helpers; and
- current manual UI/API workflows capable of creating the complete C2.1
  reference topology.

The Proxmox adapter, plugin SDK, discovery sync component, Redis service, worker
container, Integration table, and generated Markdown storage also exist. They
do not form an end-to-end live Integration journey and are not required graph
inputs.

## Documentation reviewed

Every Markdown file under `docs/**` and the root `README.md` was reviewed. The
status column describes the document's role after reconciliation.

| Document | Purpose and status | Action |
| --- | --- | --- |
| `README.md` | Current operator/developer overview | Updated manual-first sequence and Proxmox component wording |
| `AGENTS.md` | Current repository-wide agent instructions | Added after the original audit; reviewed in the 2 September delta and consistent with the audit conclusions |
| `docs/README.md` | Current documentation index and authority map | Updated C2/E status and linked this audit |
| `docs/history/product-reviews/atlas-product-feature-status-review.md` | Historical transcript-derived review dated 24 July 2026 | Retained as non-canonical evidence |
| `docs/history/product-reviews/atlas-product-feature-status-review-reconciled.md` | Historical repository-reconciled review at `09d2271` | Retained as non-canonical evidence |
| `docs/admin/knowledge-profiles.md` | Current Asset completeness administration guide | Current; no change |
| `docs/admin/service-types-and-criticality.md` | Current C1 reference-data guide | Current; no change |
| `docs/architecture/architecture-v0.md` | Implemented architecture through C1 | Updated sequencing and focused-graph authorization limitation |
| `docs/architecture/authentication-and-access-control.md` | Current security and tenancy contract | Current; remains authoritative |
| `docs/architecture/data-model-v0.md` | Foundation relational model | Updated status and added the current C1 relational extension |
| `docs/architecture/deployment-and-upgrades.md` | Current deployment, migration, backup, and rollback guidance | Current; no change |
| `docs/architecture/knowledge-changes-and-reconciliation.md` | Current evidence/accepted-knowledge architecture | Current; no change |
| `docs/architecture/knowledge-completeness.md` | Current completeness architecture | Corrected from Asset-v1 future wording to current Asset/Service coverage |
| `docs/architecture/operational-graph.md` | Planned C2.1 architecture | Updated manual input, direction, current-only temporal, and authorization rules |
| `docs/architecture/service-dependencies.md` | Current C1 dependency and focused-graph architecture | Clarified canonical direction and current route limitation |
| `docs/architecture/service-model.md` | Current C1 Service architecture | Current; no change |
| `docs/decisions/0001-shared-operational-graph.md` | Accepted future architecture decision | Retained original decision; added a dated scope clarification |
| `docs/decisions/README.md` | ADR convention and index | Current; no change |
| `docs/deployment/reverse-proxy-examples.md` | Current optional proxy examples | Current; no change |
| `docs/deployment/single-origin.md` | Current browser/API routing contract | Current; no change |
| `docs/deployment/split-origin-migration.md` | Historical/current migration guide for older deployments | Retain; no change |
| `docs/product/development-roadmap.md` | Active canonical sequence | Updated manual-first decision, C2/E classification, and temporal boundary |
| `docs/product/feature-ledger.md` | Current repository implementation audit | Re-audited at this baseline and corrected classifications/evidence |
| `docs/product/mvp-brief.md` | Historical foundation/C1 brief with current handoff | Retained and updated only at the next-sequence handoff |
| `docs/product/release-c2-plan.md` | Active implementation-ready C2.1–C2.3 plan | Updated baseline, scope, semantics, authorization, and fixture guidance |
| `docs/product/c2-readiness-audit.md` | Current reconciliation and go/no-go record | Added |
| `docs/prompts/atlas-codex-context.md` | Active implementation context | Updated baseline, manual-first strategy, and current-only temporal scope |
| `docs/prompts/c2-1-shared-operational-graph-codex-prompt.md` | Active future C2.1 implementation prompt | Updated to match this audit and remove historical-query scope |
| `docs/prompts/codex-system-instructions.md` | Historical repository workflow guidance, not runtime code | Retain; no behavioral claim changed |
| `docs/testing/auth-shell-test-plan.md` | Manual authentication/shell plan | Current plan; unchecked items are not pass evidence |
| `docs/testing/homelab-service-mvp.md` | Manual C1 acceptance plan | Current; no change |
| `docs/testing/knowledge-completeness-v1.md` | Historical/manual Asset completeness plan | Retain; current implementation extends it to Services |
| `docs/testing/knowledge-foundation-v1.md` | Historical/manual Release A/B flow | Retain as acceptance evidence |
| `docs/testing/knowledge-foundation-v2.md` | Historical/manual lifecycle flow | Retain as acceptance evidence |
| `docs/testing/release-c2-operational-graph.md` | Planned C2.1 validation contract | Updated fixture, temporal, and direction requirements |
| `docs/testing/security-and-access-test-plan.md` | Current security regression matrix | Corrected the web validation commands to include the existing unit tests |

The newly supplied product reviews are stored under the explicit
`docs/history/product-reviews/` archive path. Historical briefs, migration
guides, test plans, and the original ADR remain in their established locations
with clear roles rather than being deleted or moved.

## Supplied review reconciliation

| Previous claim or unknown | Current repository evidence | Correct classification and resolution |
| --- | --- | --- |
| C1 and its Service model were inferred implemented | Migration `20260720_0013`, `models.py`, registered Service/Business Function routers, web routes, and `test_services.py` exist | C1 implemented |
| Service-to-Asset, Service-to-Service, and Service-to-Business Function links were inferred implemented | Three temporal tables, API mutation/list routes, UI forms, assertions/changes, and tests exist | Implemented |
| Focused Service and Business Function graphs were implemented | Both GET routes and both detail-page consumers exist | Implemented focused structural projections; not a shared graph or Impact Analysis |
| Customer/site graph authorization was broadly described as complete | Focus records are scoped; Business Function expansion checks adjacent types; Service graph expansion does not consistently check every adjacent type permission | Existing route usable, with explicit C2.1 authorization hardening required |
| Full C2 or Impact Analysis was partially implemented | No shared builder, generic route, analysis semantics, scenario, scoring, or `/impact-analysis` route exists | C2.1 planned; Impact Analysis planned, not partially implemented |
| Business Function “affected Assets” implied impact | Current graph shows Function → Service → Asset structural connectivity only | Implemented connectivity; no failure/impact conclusion |
| Live Proxmox flow was implemented or uncertain | Tested plugin and sync components exist; no Integration router, secret resolver, dispatch, or worker invocation exists | B2 partially implemented; explicitly not required for C2.1 |
| Worker orchestration existed as a foundation | `apps/worker/worker/main.py` logs readiness and sleeps | Infrastructure boundary only; queue/orchestration planned |
| Integration UI status was unknown | `/integrations` imports `mock-data.js`; no Integration router is registered | Mock/scaffolded UI and persistence component; no usable management journey |
| Generated Documents were unknown/planned | `markdown_docs.py`, `Document`, sync persistence, and tests exist; no router/page exists | Implemented renderer/storage components; product surface partially implemented |
| Possible-duplicate reconciliation was uncertain | `entity_resolution.py`, reconciliation service/UI Link Asset action, and ambiguity test exist | Implemented |
| Knowledge Gap assignment was uncertain | Model column, list filters, assignment route, UI filters, and tests exist | Implemented |
| Discovery cancellation was unknown | Status enum exists; no action exists; B2 now explicitly plans cancellation | Planned but not implemented |
| Configurable second-hop focus was unknown | Current C2.1 plan commits to structural depth `0..2` | Planned but not implemented |
| Docker and PBS plugin status was unknown | No plugin packages exist; only Proxmox and SDK packages are tracked | Deferred/planned, not implemented |
| Active Integrations/Data Sources UI was uncertain | Integrations page is mock; Data Source list/create API and discovery UI exist without a standalone Connections source manager | Integration management partial; Data Source API implemented |
| Interface-first IP was implemented | `Asset.ip_address` remains in current forms/lists while interfaces are first-class | Partially implemented hardening item; outside C2.1 |
| People/Teams, Backup/Recovery, Knowledge Objects might be partially present through labels/notes | No durable domain models/routes/pages exist | Planned but not implemented; C1 labels/notes are compatibility precursors only |
| Search, notification center, installer, Portainer packaging, licence, and formal release status were unknown | No corresponding current implementation/decision is established; no `LICENSE` is tracked | Remain explicitly unknown rather than invented |

The repository-reconciled July review correctly identified most component-level
gaps. Its recommendation to complete Proxmox before C2, its old audit point,
its web test count, its optional historical `as_of` scope, and its classification
of structural graph primitives as partial Impact Analysis are superseded by
current evidence and the 30 August product decision.

## C2.1 prerequisites

| Prerequisite | Classification | Reason |
| --- | --- | --- |
| Durable Asset, Service, and Business Function nodes | Ready | Current schema, APIs, UI, and tests |
| All four edge families | Ready | Current Asset relationships plus three C1 temporal link tables |
| Accepted-versus-observed boundary | Ready | Current assertions/reconciliation architecture |
| Manual data population | Ready | Existing UI/API can create the reference topology |
| Stable graph node/edge identity | Ready with documentation correction | Namespaced rules are now consistent; implementation belongs to C2.1 |
| Canonical direction and reverse traversal semantics | Ready with documentation correction | Stored/canonical/traversal/presentation meanings are now explicit |
| Current-valid temporal membership | Ready with documentation correction | Current-only C2.1 boundary now replaces optional historical query wording |
| Shared graph builder and generic route | Requires implementation before C2.1 completion | This is the core C2.1 deliverable, not a pre-start blocker |
| Endpoint-by-endpoint graph authorization | Requires implementation before C2.1 completion | Shared builder must close the current Service route's mixed-permission gap |
| Bounded/cycle-safe/deterministic traversal | Requires implementation before C2.1 completion | Planned and test-specified; not currently implemented as a reusable service |
| Compatibility adapters | Requires implementation before C2.1 completion | Both public focused contracts must remain stable |
| B2 Integration CRUD/live Proxmox | Explicitly not required for C2.1 | Manual accepted knowledge is valid input |
| Secrets, queue, Run Now, schedules, retries, cancellation | Explicitly not required for C2.1 | B2 control-plane scope |
| Additional plugins | Explicitly not required for C2.1 | Automatic discovery is postponed for the immediate period |
| People/Teams, Knowledge Objects, Backup/Recovery | Explicitly not required for C2.1 | Later domain releases |
| Full Impact Analysis | Explicitly not required for C2.1 | Release E; structural reachability is not impact |

There is no implementation prerequisite that must be completed before C2.1 can
start. The rows marked “Requires implementation” are C2.1 acceptance work.

## C2.1 architecture readiness

| Area | Readiness conclusion |
| --- | --- |
| Graph model | Ready: typed derived projection over PostgreSQL; no second truth store |
| Semantic direction | Ready: stored/canonical source-target remains stable through incoming/reverse traversal |
| Identity | Ready: `entity_type:<uuid>` nodes and `edge_family:<uuid>` edges |
| Authorization | Design ready; implementation must authorize focus and both endpoints, omit whole inaccessible edges, and avoid count/warning leakage |
| Temporal rules | Ready: one captured request time; include `valid_from <= t` and `valid_to is null or valid_to > t`; Asset relationships are current-only |
| Bounded traversal | Ready: focus required, depth `0..2`, hard node limit, explicit safe truncation |
| Cycle handling | Ready: visited-node expansion guard without removing legitimate already-connected edges |
| Determinism | Ready: stable frontier processing and final key ordering |
| Compatibility APIs | Ready: keep current UUID-based `ServiceGraphResponse` for both focused routes through adapters |
| Testing approach | Ready: manual reference fixture plus contract, temporal, IDOR, compatibility, query-count, web, migration, and regression coverage |

PostgreSQL remains authoritative. C2.1 requires no graph persistence migration
and must not use Redis as a graph cache.

## C2.1 scope

C2.1 should implement:

- a reusable API/domain operational graph service;
- typed/namespaced Asset, Service, and Business Function nodes;
- typed/namespaced edges for Asset relationships and all C1 link families;
- current-valid accepted-knowledge membership;
- canonical direction with incoming/outgoing/both traversal;
- authorized focus and endpoint-by-endpoint expansion;
- structural depth `0..2`, node limits, deterministic truncation, and cycles;
- a generic focused graph API;
- compatibility adapters for both C1 graph routes; and
- presentation-neutral web utilities and the specified tests.

C2.1 may answer what is connected, which Services use an Asset, what Assets
support a Service, which Services depend on another Service, which Business
Functions are linked, and what bounded structural path connects known entities.

C2.1 must not implement or claim:

- failure propagation, outage probability, or blast radius;
- business impact severity or single-point-of-failure conclusions;
- recovery order, readiness, duration, or protection adequacy;
- change safety or intended-state simulation;
- dependency groups, quorum, redundancy, or failure effects;
- caller-selected historical graph reconstruction;
- B2 Integration/worker/plugin work;
- People/Teams, Knowledge Objects, or Backup/Recovery; or
- a graph database or persisted duplicate graph.

## Manual reference dataset

Use a synthetic `Home / Homelab` context plus a second customer and second Site.
Create through current UI/API capabilities:

- Assets: gateway, switch, PVE1/PVE2/PVE3, NAS, PBS, Authentik LXC,
  Authentik Application Asset, Atlas LXC, Grafana LXC, and an isolated Asset;
- Services: Authentication, DNS, Infrastructure Knowledge, Monitoring, and
  Photo Management;
- Business Functions: Secure Access, Monitoring and Administration, and
  Household Information;
- Asset relationships for physical, hosting, storage, and dependency structure;
- Service-to-Asset dependencies, including the Application Asset and several
  infrastructure Assets;
- Service-to-Service dependencies with multiple upstream inputs, multiple
  downstream dependants, and one legitimate two-Service cycle; and
- Service-to-Business-Function links.

Include customer-wide and Site-scoped Services, similarly named inaccessible
records, direct-ID substitutions, and at least one relationship whose adjacent
entity permission is deliberately absent. This is fixture guidance, not a
hard-coded production taxonomy.

## Parallel and deferred work

- **B2 Operational Integrations:** incomplete and tracked separately; not a
  C2.1 gate.
- **Plugin expansion:** postponed; Proxmox adapter remains intact.
- **Scheduler/worker control plane:** postponed with secrets, Run Now, retries,
  cancellation, and scheduling.
- **People/Teams:** Release C3.
- **Knowledge Objects:** Release C4.
- **Backup & Recovery:** Release D.
- **Full Impact Analysis:** Release E, after dependency semantics and analysis
  primitives.
- **Documents UI and intended state:** later F work; renderer/storage components
  remain intact.
- **Interface-first IP cleanup:** independent foundation hardening.

## Validation

Executed at the audited code baseline:

| Check | Result |
| --- | --- |
| API pytest suite | 158 passed; 464 Python 3.14/FastAPI deprecation warnings |
| Web Node test suite | 70 passed |
| Next.js production build | Passed; 32 routes generated |
| Plugin SDK + Proxmox pytest suites | 27 passed |
| Alembic heads | One: `20260720_0013` |
| Alembic current / live migration | Not run: no PostgreSQL or Docker executable is available in this environment |
| Docker/Compose acceptance | Not run: Docker executable unavailable |
| Documentation relative-link check | Passed after documentation edits |
| `git diff --check` | Passed after documentation edits |

The Python suite was run in a disposable `/private/tmp` virtual environment.
No application dependency files or C2 functionality were changed. The only
application-code edit is a terminology correction on the existing Business
Function page from impact language to structural connectivity language.

Delta validation on 2 September 2026 was limited to the documentation changes:
`git diff --check` passed, and every relative link added by the delta resolved.
Application tests and the production frontend build were not rerun because the
delta changed documentation only and the committed application tree is
unchanged from the previously validated audit commit.

## Go / No-Go conclusion

**GO — repository and architecture are sufficiently aligned to begin C2.1.**

No unrelated B2/plugin work blocks the start. C2.1 must deliver its shared
builder, strict endpoint authorization, bounded deterministic traversal, and
compatibility adapters before it can be called complete. Full Impact Analysis
remains a later release.
