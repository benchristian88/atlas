# Atlas product feature ledger — repository-reconciled edition

**Repository audit date:** 30 August 2026
**Review comparison dates:** 23–24 July 2026
**Planning alignment update:** 30 August 2026
**Repository source of truth:** `dev` at `4b0bfac6c746c56df9e1bfe16bae33d8dff3721e`
**Primary evidence:** audited repository models, migrations, routes, pages, tests, and build configuration
**Comparison baseline:** the earlier transcript-derived **Atlas Product Feature Status Review**

> **Authority of this ledger**
>
> The earlier review inferred implementation from completed Codex prompts and user acceptance.
> This revised edition treats the audited repository as authoritative.
>
> A completed prompt is evidence that work was requested and probably attempted. It is **not**
> enough to classify a feature as implemented unless the repository contains the necessary
> schema, reachable backend path, usable frontend path where applicable, and supporting tests.


---

# 0. Repository and planning alignment update — 30 August 2026

This update re-audits the current `dev` tree. Commits after `09d2271` changed
documentation and planning, not application code, but the implementation
classifications and validation counts below were checked again at the current
commit. The July reviews remain historical comparison evidence.

The following planning decisions are now recorded:

1. **C2.1 — Shared Operational Graph is the selected next development increment.**
   This is a sequencing decision, not a change to repository status.
2. **The immediate product strategy is manual-first.** Manually entered and
   curated accepted knowledge will be used to prove the model before major
   further automatic-discovery investment.
3. **B2 — Operational Integrations and live discovery remains an incomplete
   parallel workstream, not a C2.1 prerequisite.** C2.1 must not absorb
   Integration CRUD, secret resolution, worker dispatch, live Proxmox
   execution, scheduling, retries, or cancellation.
4. **Release C2 is decomposed for delivery:**
   - C2.1 — Shared Operational Graph;
   - C2.2 — Dependency Semantics; and
   - C2.3 — Analysis Primitives.
5. **F1 — Documentation Experience may be delivered independently** because the
   repository already contains deterministic Asset Markdown generation and
   `Document` persistence. It is not a prerequisite for C2.1.
6. **Foundation hardening remains visible outside the principal release chain,**
   especially the Interface-first IP transition and replacement of the mock
   Integrations page.
7. The shared graph remains a derived, API-owned projection over accepted
   relational knowledge. PostgreSQL remains the system of record, and C2.1 does
   not introduce impact, recovery, availability, or change-safety conclusions.

The canonical forward sequence is maintained in
[`development-roadmap.md`](development-roadmap.md). The implementation prompt is
maintained in
[`../prompts/c2-1-shared-operational-graph-codex-prompt.md`](../prompts/c2-1-shared-operational-graph-codex-prompt.md).

---

# 1. Status definitions

| Status | Meaning used in this ledger |
|--------|-----------------------------|
| **Implemented** | The audited repository contains a usable capability across the layers it needs. Durable features have schema/migration evidence and reachable code paths; interactive features have a usable current UI. |
| **Partially implemented** | Meaningful layers exist, but the requested product journey is not end-to-end or an important part is missing. |
| **Planned but not implemented** | Roadmap, navigation, architecture or next-increment documentation commits to the capability, but no usable implementation exists. |
| **Deferred** | Explicitly excluded from the MVP/C1 scope or intentionally postponed. |
| **Abandoned** | A previous approach or product surface was deliberately superseded or rejected. |
| **Unknown** | The repository anticipates or mentions the capability, but neither implementation nor a clear current product decision exists. |


---

# 2. Executive assessment

## What the earlier review got broadly right

The earlier transcript-based review correctly identified that Atlas has implemented:

* the platform and deployment foundation;
* local authentication, scoped RBAC and customer/site context;
* inventory, networks, interfaces, relationships and managed reference data;
* the Knowledge Foundation;
* simulated discovery, reconciliation and no-longer-observed handling;
* Knowledge Changes and Asset fact history;
* configurable Asset and Service completeness;
* a dedicated Knowledge Gaps workflow;
* first-class Services, Business Functions and typed dependencies;
* focused Service and Business Function graph projections;
* the recent UI and navigation refinements.

It also correctly identified that the following remain future work:

* People and Teams;
* structured Service ownership;
* full Impact Analysis;
* Backup and Recovery workflows;
* formal Knowledge Objects;
* SSO/MFA;
* deeper plugin integrations;
* automatic conversion of legacy Service Assets.

## Where the earlier review overstated the implementation

The repository audit materially changes several classifications:


1. **End-to-end Proxmox discovery is only partially implemented.**
   The plugin, normalizer and core sync exist, but there is no configured
   Integration → secret resolution → plugin invocation → worker dispatch journey.
   The usable discovery product path is still JSON simulation.
2. **Worker orchestration is only partially implemented.**
   Redis and a worker container exist, but the worker only logs readiness and sleeps.
   There is no queue, scheduler, retry, cancellation or job-control implementation.
3. **Generated Documentation is only partially implemented.**
   Atlas can generate and store deterministic Asset Markdown, but users cannot browse
   it because there is no documents router or documents UI.
4. **Impact Analysis is not implemented.** Focused structural graphs and one-hop
   dependency views are real prerequisites, but they do not calculate impact.
   Recursive analysis, outage semantics, evidence paths, scoring and a dedicated
   route do not exist.
5. **Integration management is only partially implemented.**
   The Integration model and navigation scaffolding exist, but the page still uses mock data
   and there is no registered Integration API router.
6. **Business Function lifecycle is only partially implemented.**
   Business Functions exist, but they do not yet have their own assertions,
   completeness profiles, gap summaries or change history.
7. **The Interface-first IP transition is incomplete.**
   Interfaces and topology use structured IP data, but Asset forms/lists still expose
   the legacy direct `Asset.ip_address`.

## Current release position

| Release area | Repository-grounded status |
|--------------|----------------------------|
| Platform / inventory foundation | **Implemented**            |
| Release A — Knowledge Foundation | **Implemented**            |
| Release B — Discovery and Reconciliation | **Implemented for simulation and reconciliation; live plugin operation is partial** |
| B.5 — Knowledge Completeness | **Implemented for Assets and Services** |
| Release C1 — Homelab Service MVP | **Implemented**            |
| Release C2 — shared graph and later analysis foundations | **Planned; C1 focused projections are precursors**  |
| Release C3 — People, Teams and structured ownership | **Planned but not implemented** |
| Release C4 — formal Knowledge Objects | **Planned but not implemented** |
| Release D — Backup and Recovery | **Planned but not implemented** |
| Release E — full Impact Analysis | **Planned but not implemented; structural prerequisites exist** |
| Release F — Documentation and intended state | **Partially implemented foundation; user-facing product not implemented** |
| Production/community release packaging | **Not established by the repository ledger** |


---

# 3. Expected-versus-actual correction matrix

This section records the most important differences between the earlier
transcript-derived report and the audited repository.

| Feature area | Earlier expected classification | Actual repository classification | Concrete reason |
|--------------|---------------------------------|----------------------------------|-----------------|
| End-to-end Proxmox discovery | Implemented or uncertain        | **Partially implemented**        | Plugin discovery/normalization and `AtlasDiscoverySync` exist, but no API/worker path loads an Integration, resolves a secret and invokes the plugin. |
| Redis worker orchestration | Implemented foundation / limited | **Partially implemented**        | Compose runs Redis and worker, but `worker/main.py` only logs readiness and sleeps. |
| Integration management UI | Unknown/partially implemented   | **Partially implemented**        | Integration table and permissions exist; `/integrations` still imports mock data and no Integration router is registered. |
| Generated Documentation | Planned/unknown                 | **Partially implemented**        | Deterministic Asset Markdown and `Document` persistence exist, but no documents router or usable UI exists. |
| Impact Analysis | Planned but not implemented     | **Planned but not implemented**  | Focused Service/Business Function graphs are structural prerequisites, not an impact engine; no outage semantics or `/impact-analysis` exists. |
| Business Function completeness/history | Not separately classified       | **Partially implemented**        | Business Function CRUD and graph exist, but no assertions, profiles, gaps or history. |
| Interface-first IP UX | Implemented                     | **Partially implemented**        | Interfaces are first-class, but Asset forms and list still use direct `ip_address`. |
| Discovery cancellation | Assumed part of lifecycle       | **Planned but not implemented**  | `cancelled` is a valid status and B2 now commits to cancellation, but no cancel endpoint, UI, action, or test exists. |
| Full Reconciliation action set | Broadly treated as implemented  | **Core decisions implemented; some advanced actions not evidenced** | Accept/reject/defer/lifecycle paths are tested; reclassify, bulk operations and broad merge journeys are not present. |
| Full Documentation product | Planned but not implemented     | **Partially implemented**        | The renderer and storage are already real, but the product surface is absent. |
| Service graph | Implemented                     | **Implemented as focused graph only** | `/services/{id}/graph` and `/business-functions/{id}/graph` exist; architecture deliberately limits recursion. |
| Service C1   | Implemented                     | **Implemented**                  | Migration `20260720_0013`, Services routes/pages/tests and Business Functions confirm the full C1 slice. |
| Knowledge Gaps | Implemented                     | **Implemented**                  | Dedicated APIs, assignment/defer/exception/reopen/resolve and URL-backed UI are all present. |
| Profile/avatar | Implemented initials support; photo deferred | **Same**                         | Account menu and initials/image fallback exist; no avatar field/upload endpoint. |
| Global graph database | Abandoned                       | **Same**                         | PostgreSQL remains the chosen architecture. |
| Legacy Service Asset conversion | Deferred/abandoned for C1       | **Same**                         | Explicitly retained without automatic migration. |


---

# 4. Repository validation evidence

The Feature Ledger records the following audit checks:

* API tests: **158 passed**
* Web unit/regression tests: **70 passed**
* Plugin SDK and Proxmox tests: **27 passed**
* Next.js 16.2.10 production build: **passed**
* Generated static pages: **32**
* Alembic heads: **one**
* Current migration head: `20260720_0013`
* Markdown links: **passed**
* `git diff --check`: **passed**

These checks were rerun on 30 August 2026 at the current audit commit. The API
suite emitted 464 Python 3.14/FastAPI deprecation warnings but no failures.

They do **not** establish:

* a live configured PostgreSQL/Docker acceptance run at audit time;
* a live Proxmox integration run through the Atlas UI;
* production queue behavior;
* secret-store resolution;
* community installer behavior.


---

# 5. Detailed feature inventory

## 5.1 Runtime, deployment and platform foundation

| Feature | Status | Release | Concrete evidence |
|---------|--------|---------|-------------------|
| Monorepo runtime scaffold | **Implemented** | Foundation | Compose defines API, web, worker, PostgreSQL and Redis; FastAPI exposes `/api/health`; the worker logs readiness. |
| PostgreSQL durable schema | **Implemented** | Foundation | `models.py` and a linear 13-revision Alembic chain provide the current schema. |
| Additive database upgrades | **Implemented** | Foundation | Migration history includes safe backfills for Sites, managed types, user access, knowledge and Services. |
| Single-origin `/api`deployment | **Implemented** | Production foundation | All routers mount below `/api`; browser API URL defaults to `/api`; tests cover namespaced routes. |
| Optional split-origin development | **Implemented** | Development compatibility | Configurable CORS and absolute API URL overrides are tested. |
| Production Next.js start | **Implemented** | Production foundation | Current web image uses the production Next.js start command. |
| Redis service boundary | **Implemented as infrastructure** | Foundation | Redis is present in Compose and configured for the worker. |
| Redis-backed job processing | **Partially implemented** | Future worker increment | No queue client, producer, consumer, retry, scheduling, cancellation or job status exists. |
| Long-running worker container | **Partially implemented** | Foundation/future | Worker starts and stays alive but performs no operational work. |
| Upgrade/backfill compatibility | **Implemented** | Production foundation | Migrations preserve legacy records and do not reset the database. |
| Full production scheduler/control plane | **Deferred** | Later production hardening | Explicit MVP non-goal. |
| Community Proxmox LXC installer | **Unknown** | Community release | Not covered by the audited repository ledger. |
| Portainer-ready GitHub Compose path | **Unknown** | Community release | Not established by the ledger. |
| Formal 0.1 packaging/licensing | **Unknown** | Community release | Not established by the ledger. |


---

## 5.2 Authentication, access and account experience

| Feature | Status | Release | Concrete evidence |
|---------|--------|---------|-------------------|
| Local email/password authentication | **Implemented** | Foundation | Password hashing, login, logout, `/auth/me`, profile and password-change routes exist and are tested. |
| Argon2 password hashing | **Implemented** | Foundation | Auth tests verify hashing behavior. |
| HttpOnly cookie sessions | **Implemented** | Foundation | `atlas_session` uses HttpOnly/SameSite and the browser sends credentials. |
| Bearer-token API compatibility | **Implemented** | Foundation compatibility | API accepts bearer credentials as well as session cookies. |
| Browser localStorage bearer sessions | **Abandoned** | Superseded design | Replaced by HttpOnly cookie sessions; legacy token code only removes old values. |
| One-time administrator bootstrap | **Implemented** | Foundation | `seed_admin.py` creates only the first forced-change Master Administrator and is idempotent. |
| Forced password change | **Implemented** | Foundation | Backend restrictions and Profile flow exist. |
| Admin temporary-password reset | **Implemented** | Foundation | Admin user page supports write-only reset. |
| Protected application shell | **Implemented** | Foundation | Session states prevent protected content flashing and handle failures cleanly. |
| Scoped RBAC | **Implemented** | Foundation | Stable permission keys and global/customer/site Access Assignments are enforced server-side. |
| Viewer read-only role behavior | **Implemented** | Foundation | Covered by CRUD/administration tests. |
| Last-Master protection | **Implemented** | Foundation | Administration tests verify protections. |
| Customer/site context selector | **Implemented** | Foundation | Context API, workspace context and revalidation are present. |
| User/role/assignment administration | **Implemented** | Foundation | Guarded APIs and administration pages exist. |
| Per-user accent preference | **Implemented** | UI/account | Persisted, validated and tested. |
| Top-right account menu | **Implemented** | UI/account | Profile/logout dropdown exists and is tested. |
| Initials/image fallback avatar | **Implemented** | UI/account | `user-avatar.js` provides safe fallback behavior. |
| Avatar/photo upload | **Deferred** | Future account work | No avatar field, media storage or upload endpoint exists. |
| SSO/OIDC/SAML | **Planned but not implemented** | Production security | Extension fields exist, but no issuer/callback flow exists. |
| MFA     | **Planned but not implemented** | Production security | `mfa_enabled` is only an extension field; no enrollment/challenge workflow exists. |
| Forgotten-password email | **Deferred** | Future account work | Explicitly absent in security limitations. |
| Recovery codes | **Deferred** | Future account work | No recovery-code model or route. |
| Per-device session management | **Deferred** | Future account work | Current model has user-level session generation only. |
| Break-glass recovery command | **Deferred** | Production hardening | Explicitly documented as not existing. |
| External append-only audit export | **Planned but not implemented** | Production hardening | Current audit remains PostgreSQL-backed only. |
| Arbitrary per-record policy | **Deferred** | Enterprise authorization | Explicit MVP non-goal. |
| Delegated role administration | **Deferred** | Enterprise authorization | Explicit MVP non-goal. |


---

## 5.3 Inventory, reference data and topology

| Feature | Status | Release | Concrete evidence |
|---------|--------|---------|-------------------|
| Customer CRUD | **Implemented** | Foundation | Models, routes and pages use real APIs. |
| Site CRUD | **Implemented** | Foundation | Models, routes and pages use real APIs. |
| Manual Asset CRUD | **Implemented** | Foundation | Scoped APIs and create/detail/edit UI exist. |
| Managed Asset Types | **Implemented** | Foundation | Stable-key database records and administration UI exist. |
| Asset Type safe lifecycle | **Implemented** | Foundation | Inactive and referenced deletion behavior is tested. |
| Managed Relationship Types | **Implemented** | Foundation | Database-managed labels/direction/type constraints exist. |
| Relationship endpoint applicability | **Implemented** | C1      | Supports Asset→Asset, Service→Asset, Service→Service and Service→Business Function. |
| Typed Custom Fields | **Implemented** | Foundation | Definition, applicability, options and values are implemented. |
| Ten-field active limit per type | **Implemented** | Foundation | Enforced and tested. |
| Customer-specific taxonomies | **Deferred** | Enterprise/MSP | Asset/Relationship Types and Custom Field definitions remain global. |
| Asset/type icons | **Implemented** | Foundation/UI | Safe HTTPS non-SVG icon handling and fallback exist. |
| Uploaded icon/media library | **Deferred** | Future media system | No blob/media route or storage. |
| Server-side icon proxy | **Deferred** | Future media system | No remote fetch/proxy. |
| Atlas Impact branding in shell/login | **Implemented** | UI      | Shared supplied lockups are theme-aware in the shell and used on login. |
| Runtime/customer-specific branding | **Deferred** | Future enterprise branding | Current branding is build-time. |
| Networks/VLAN CRUD | **Implemented** | Foundation | Customer/site/type/VLAN/CIDR/gateway/purpose/zone/notes are persisted. |
| Asset Interfaces | **Implemented** | Foundation | Interface, network, IP, MAC, primary and notes are persisted and managed. |
| Direct Asset IP field | **Partially superseded** | Foundation migration | Remains in forms/lists for compatibility even though interfaces are first-class. |
| Interface-first IP UX | **Partially implemented** | Future polish | Topology/detail use interfaces; create/edit/list still prioritise direct `ip_address`. |
| Safe CIDR membership suggestions | **Unknown** | Network UX | No implementation or explicit decision. |
| Asset Relationships | **Implemented** | Foundation | Scoped CRUD, type validation and same-context rules exist. |
| New cross-site/customer relationships | **Deferred/prohibited** | Security boundary | Explicitly rejected and tested. |
| Legacy cross-context relationships | **Implemented as compatibility** | Migration support | Readable only when both endpoints are authorised. |
| Knowledge Graph topology API | **Implemented** | Foundation | Returns authorised Assets, relationships, networks and interfaces. |
| Physical lens | **Implemented** | Foundation/UI | Current topology lens. |
| Platform lens | **Implemented** | Foundation/UI | Current topology lens. |
| Network/VLAN lens | **Implemented** | Foundation/UI | Current topology lens. |
| Dependency lens | **Implemented** | Foundation/UI | Supports one-hop focus. |
| All Relationships lens | **Implemented** | Foundation/UI | Current topology lens. |
| Old generic hierarchy tabs | **Abandoned** | UI supersession | Replaced by the current lenses. |
| Second-hop topology focus | **Planned but not implemented** | C2.1 | The shared operational graph plan permits structural depth `0..2`; current topology focus remains direct neighbours. |
| Live Dashboard summaries | **Implemented** | Foundation/C1 | Inventory, relationship, Service, Business Function and completeness totals are live. |


---

## 5.4 Knowledge Foundation, discovery simulation and reconciliation

| Feature | Status | Release | Concrete evidence |
|---------|--------|---------|-------------------|
| Data Source model | **Implemented** | A/B     | Durable DataSource records exist. |
| Data Source list/create API | **Implemented** | A/B     | Knowledge router exposes list/create. |
| Simulated discovery | **Implemented** | B       | `/discovery/simulate` and UI provide a usable JSON path. |
| Discovery Run list/detail | **Implemented** | B       | Durable run records and pages exist. |
| EvidenceRecord | **Implemented** | A       | Durable table and APIs exist. |
| KnowledgeAssertion | **Implemented** | A       | Durable table, UI and tests exist. |
| ReconciliationItem | **Implemented** | B       | Durable table, queues and decisions exist. |
| Accept reconciliation | **Implemented** | B       | Tested for Asset/fact/relationship acceptance. |
| Reject reconciliation | **Implemented** | B       | Tested.           |
| Defer reconciliation | **Implemented** | B       | Tested.           |
| Lifecycle decisions | **Implemented** | B       | No-longer-observed decisions are tested. |
| Bulk reconciliation acceptance | **Deferred** | Future B enhancement | Explicitly excluded from Knowledge Foundation v2. |
| EntitySourceLink | **Implemented** | A/B     | Exact/manual source identity mapping exists. |
| External identity matching | **Implemented** | B       | Exact/manual matching and ambiguity metadata are tested. |
| Relationship endpoint resolution | **Implemented** | B       | Reconciliation preserves unresolved/ambiguous endpoint metadata. |
| JSON-safe knowledge metadata | **Implemented** | A/B     | UUID/datetime/Enum/Pydantic values are normalised before persistence. |
| Discovery Run archive/restore/delete | **Implemented** | B       | Dependency-aware lifecycle behavior exists. |
| Assertion retraction | **Implemented** | A       | Reasoned retraction exists without removing accepted operational data. |
| Historical assertion read resilience | **Implemented** | A       | Missing optional provenance does not break reads. |
| Complete snapshot coverage | **Implemented** | B       | Coverage keys and baseline comparison exist. |
| No-longer-observed detection | **Implemented** | B       | Valid complete baselines create reviewable absence episodes. |
| Partial-run protection | **Implemented** | B       | Partial/failed/different coverage is tested not to cause absence. |
| Re-observation | **Implemented** | B       | Re-observed entities resolve prior absence. |
| Automatic deletion of absent Assets | **Deferred/prohibited** | Product rule | Assets become stale/reviewable; they are not deleted automatically. |
| Automatic rollback when deleting a run | **Deferred** | Future reconciliation reversal | Explicitly not performed. |
| Meaningful Changes timeline | **Implemented** | A/B     | Semantic changes and compact UI exist. |
| Asset fact history | **Implemented** | A       | API and UI exist. |
| Source-current vs accepted knowledge | **Implemented** | A hardening | Predicate cardinality and accepted/current distinctions exist. |
| Manual edits as declared accepted assertions | **Implemented** | A       | Assets and Services create accepted declarations. |
| Predicate roll-up | **Implemented** | A       | Asset detail defaults to a concise summary while preserving history/raw views. |
| Discovery cancellation state value | **Implemented as schema only** | B       | `cancelled` is allowed as a status. |
| Discovery cancellation workflow | **Planned but not implemented** | B2 worker work | B2 commits to cancellation, but no cancel API/page/action/test exists. |
| Start/retry operational run API | **Partially implemented/absent** | Future worker work | Simulation starts runs; configured operational jobs do not exist. |
| Full worker-dispatched discovery lifecycle | **Partially implemented** | Future B hardening | Run schema exists but job dispatch does not. |


---

## 5.5 Knowledge Completeness and Knowledge Gaps

| Feature | Status | Release | Concrete evidence |
|---------|--------|---------|-------------------|
| Configurable Asset knowledge profiles | **Implemented** | B.5     | Requirement, Gap and Summary tables plus evaluator exist. |
| Database-defined structured rules | **Implemented** | B.5     | Rules are validated against bounded supported vocabulary. |
| Arbitrary executable expressions | **Deferred/prohibited** | B.5 design | Explicitly excluded. |
| Automatic reevaluation triggers | **Implemented** | B.5     | Asset/relationship/service changes trigger evaluation. |
| Evaluator failure isolation | **Implemented** | B.5     | Tests cover isolation. |
| Stable/idempotent summaries | **Implemented** | B.5     | Tests cover idempotence. |
| Dedicated Knowledge Gaps route | **Implemented** | B.5     | Separate APIs and `/knowledge-gaps` UI exist. |
| Gap list and summary | **Implemented** | B.5     | Routes provide both. |
| Gap defer | **Implemented** | B.5     | API/UI exists.    |
| Gap exception | **Implemented** | B.5     | API/UI exists.    |
| Gap reopen | **Implemented** | B.5     | API exists.       |
| Gap assign | **Implemented** | B.5     | API supports assignment. |
| Gap resolve | **Implemented** | B.5     | API supports resolution. |
| URL-backed filters | **Implemented** | UI refinement | Filter tests cover state and separation. |
| Compact Knowledge Gap cards | **Implemented** | UI refinement | Current page includes the requested compact card design. |
| Knowledge Gaps separate from Reconciliation | **Implemented** | Architecture/UI | Tests assert no Missing Knowledge reconciliation queue. |
| Asset completeness panel | **Implemented** | B.5     | Asset detail/list/dashboard consume results. |
| Service completeness | **Implemented** | C1      | Service Types have knowledge profiles and Service gaps appear in the same workflow. |
| Business Function completeness | **Partially implemented/absent** | Future extension | Business Functions lack assertions, profiles, summaries and gaps. |
| Asset owner existence rule | **Deferred** | C3 dependency | Explicitly disabled until a structured ownership model exists. |
| AI-generated remediation | **Deferred/prohibited** | Product principle | Remediation hints are administrator-authored. |


---

## 5.6 Services and Business Functions

| Feature | Status | Release | Concrete evidence |
|---------|--------|---------|-------------------|
| First-class Service records | **Implemented** | C1      | Migration, routes and full list/create/detail/edit UI exist. |
| Service archive/restore | **Implemented** | C1      | API supports both. |
| Service Types | **Implemented** | C1      | Managed reference records and admin UI exist. |
| Criticality Levels | **Implemented** | C1      | Managed reference records and admin UI exist. |
| Suggested RTO/RPO | **Implemented** | C1      | Criticality defaults exist without overwriting explicit values. |
| Purpose | **Implemented** | C1      | Persisted and displayed. |
| Lifecycle/operational status | **Implemented** | C1      | Persisted and displayed. |
| Simple owner label | **Implemented** | C1      | Persisted as a Service field. |
| Technical contact label | **Implemented** | C1      | Persisted as a Service field. |
| Support group label | **Implemented** | C1      | Persisted as a Service field. |
| RTO in exact minutes | **Implemented** | C1      | Conversion and validation are tested. |
| RPO in exact minutes | **Implemented** | C1      | Conversion and validation are tested. |
| Backup/recovery notes | **Implemented** | C1      | Persisted and shown. |
| Runbook URL | **Implemented** | C1      | Lightweight link exists. |
| Documentation URL | **Implemented** | C1      | Lightweight link exists. |
| Service→Asset dependencies | **Implemented** | C1      | Typed temporal dependency model/API/UI exists. |
| Service→Service dependencies | **Implemented** | C1      | Typed temporal dependency model/API/UI exists. |
| Service→Business Function links | **Implemented** | C1      | Typed temporal link model/API/UI exists. |
| End dependency without deleting history | **Implemented** | C1      | `valid_from`/`valid_to` are preserved. |
| Service provenance | **Implemented** | C1      | Fields/links create accepted assertions and changes. |
| Service completeness | **Implemented** | C1      | Evaluator, profiles and gaps are integrated. |
| Business Function CRUD | **Implemented** | C1      | Scoped create/list/detail/edit exists. |
| Business Function owner/criticality fields | **Implemented** | C1      | Lightweight labels/criticality exist. |
| Supporting Services | **Implemented** | C1      | Detail view shows linked Services. |
| Connected Assets through Services | **Implemented** | C1      | Business Function detail exposes structural connectivity without claiming impact. |
| Business Function assertions/history | **Partially implemented/absent** | Future C extension | No first-class assertions, completeness or change-history page. |
| Focused Service graph | **Implemented with C2.1 authorization hardening required** | C1 | `/api/services/{id}/graph` is reachable, but current route assembly does not independently check every adjacent entity type's view permission. |
| Focused Business Function graph | **Implemented** | C1      | `/api/business-functions/{id}/graph` exists and checks projected Service and Asset viewability. |
| Recursive global Service graph | **Deferred** | C2/E    | Explicitly outside C1. |
| Application Asset retained | **Implemented/design decision** | C1      | First-class Service is distinct from deployed Application Asset. |
| Legacy Service Asset retained | **Implemented as compatibility** | C1      | It is not silently converted. |
| Automatic legacy Service conversion | **Deferred/prohibited** | Future association work | No automatic migration or duplicate creation. |
| Deliberate Asset-to-Service association assistant | **Planned but not implemented** | C2/C3   | Architecture says it should come later. |


---

## 5.7 Plugins, integrations and operational discovery

| Feature | Status | Release | Concrete evidence |
|---------|--------|---------|-------------------|
| Vendor-neutral plugin SDK | **Implemented** | Integration foundation | Contracts for validate/discover/normalize/sync exist and are tested. |
| Credential-safe plugin representations | **Implemented** | Integration foundation | Tests verify secrets are not exposed. |
| Proxmox API-token connection adapter | **Implemented** | Integration foundation | HTTPS/token/TLS validation and sanitised failures are tested. |
| Proxmox node discovery | **Implemented as adapter** | Integration foundation | Plugin collects nodes. |
| Proxmox QEMU VM discovery | **Implemented as adapter** | Integration foundation | Plugin collects QEMU VMs. |
| Proxmox LXC discovery | **Implemented as adapter** | Integration foundation | Plugin collects LXCs. |
| Proxmox storage discovery | **Implemented as adapter** | Integration foundation | Plugin collects storage pools. |
| Proxmox bridge discovery | **Implemented as adapter** | Integration foundation | Plugin collects bridges. |
| Proxmox vendor-neutral normalisation | **Implemented** | Integration foundation | Stable Assets/facts/relationships are produced. |
| Idempotent core discovery sync | **Implemented as component** | Integration foundation | Raw payload retention, upsert, last-seen and stale marking are tested. |
| Integration persistence model | **Implemented** | Integration foundation | Integration table stores plugin and connection metadata. |
| Integration management API | **Partially implemented/absent** | Future integration increment | No Integration router is registered. |
| Integration management page | **Partially implemented** | Future integration increment | Page exists but imports mock data. |
| Test-connection journey | **Partially implemented/absent** | Future integration increment | Standalone validator exists; no current user journey invokes it. |
| Integration secret resolver/store | **Unknown** | Production integration | `secret_reference` exists, but no provider/resolver contract is decided. |
| End-to-end configured Proxmox run | **Partially implemented** | B hardening | No path joins Integration, secret resolution, plugin and worker dispatch. |
| JSON simulated discovery | **Implemented** | B       | Current usable discovery input. |
| Automatic worker dispatch | **Partially implemented/absent** | B hardening | Worker does not dispatch plugins. |
| Scheduled discovery | **Deferred** | Future worker control plane | No scheduler or queue controls. |
| PBS plugin | **Deferred** | Later integration/D | Source type is reserved; no plugin package exists. |
| Docker plugin | **Deferred** | Later integration | Source type is reserved; no plugin package exists. |
| UniFi plugin | **Deferred** | Later integration | Source type is reserved; no plugin package exists. |
| NetBox plugin | **Deferred** | Later integration/F | Source type is reserved; no plugin package exists. |
| Imported-file adapter | **Deferred/absent** | Later integration | Source type is reserved only. |
| Additional vendor plugins | **Deferred** | Post-MVP | Explicitly deferred beyond Proxmox. |
| Plugin ingestion worker identity | **Planned but not implemented** | Production integration | No service identity or queued authorisation envelope exists. |


---

## 5.8 Generated Documentation

| Feature | Status | Release | Concrete evidence |
|---------|--------|---------|-------------------|
| Deterministic Asset Markdown renderer | **Implemented as component** | F foundation | `markdown_docs.py` renders sanitised deterministic Asset Markdown. |
| Relationship rendering in Markdown | **Implemented as component** | F foundation | Tests cover relationship rendering. |
| Injection-resistant Markdown output | **Implemented as component** | F foundation | Tests cover sanitisation. |
| Document persistence | **Implemented as storage** | F foundation | Core sync upserts `Document` rows. |
| Discovery-run document linkage | **Implemented as storage** | F foundation | Generated documents are linked to runs. |
| Documents API router | **Partially implemented/absent** | F       | No documents router is registered. |
| Document list page | **Partially implemented/absent** | F       | Navigation remains unavailable. |
| Document detail page | **Partially implemented/absent** | F       | No usable user surface. |
| User editing of generated docs | **Planned but not implemented** | F       | No product surface or editing workflow. |
| Service documentation generation | **Planned but not implemented** | F       | Current renderer is Asset-focused. |
| Site architecture documents | **Planned but not implemented** | F       | No usable implementation. |
| Recovery documents | **Planned but not implemented** | D/F     | Recovery domain does not exist. |
| Impact reports | **Planned but not implemented** | E/F     | Full impact engine does not exist. |
| Formal Knowledge Object model | **Planned but not implemented** | C4/F    | Architecture anticipates future associations. |
| Runbook as first-class object | **Planned but not implemented** | C4/D    | Current Service stores only URL/notes. |
| Decision object | **Planned but not implemented** | C4      | No model/router/page. |
| Assumption object | **Planned but not implemented** | C4      | No model/router/page. |
| Exception knowledge object | **Planned but not implemented** | C4      | Gap exceptions exist, but not formal reusable knowledge objects. |


---

## 5.9 Impact Analysis and Recovery

| Feature | Status | Release | Concrete evidence |
|---------|--------|---------|-------------------|
| One-hop dependency focus | **Implemented as structural navigation** | C1 | Asset topology and Service graphs expose direct links without impact conclusions. |
| Service “Depends on” / “Required by” | **Implemented** | C1      | Typed Service dependencies exist. |
| Business Function connected Assets | **Implemented** | C1 | Business Function detail and graph expose Assets connected through supporting Services; this is not impact analysis. |
| Focused Service projection | **Implemented** | C1 | Structural graph endpoint exists. |
| Recursive analysis traversal | **Planned but not implemented** | C2.3/E | No recursive impact engine. C2.1 bounded structural projection is not impact propagation. |
| Depth limits/cycle-aware traversal engine | **Planned but not implemented** | C2/E    | Current architecture deliberately avoids deep recursion. |
| Outage simulation | **Deferred** | E       | Explicitly excluded from C1. |
| Dedicated `/impact-analysis` route | **Planned but not implemented** | E       | Navigation entry is unavailable. |
| Evidence-qualified impact path | **Planned but not implemented** | E       | No path/evidence engine. |
| Confidence-qualified impact | **Planned but not implemented** | E       | No scoring/qualification layer. |
| Blast radius | **Planned but not implemented** | E       | No workflow or route. |
| Impact scoring | **Planned but not implemented** | E       | No scoring engine. |
| Recovery readiness | **Planned but not implemented** | D/E     | Service completeness is a precursor only. |
| Backup Policy | **Planned but not implemented** | D       | No model/router/page. |
| Backup Job | **Planned but not implemented** | D       | No model/router/page. |
| Backup Run/Copy | **Planned but not implemented** | D       | No model/router/page. |
| Backup Repository | **Planned but not implemented** | D       | PBS may be an Asset, not a structured repository. |
| Recovery Plan | **Planned but not implemented** | D       | No model/router/page. |
| Recovery Step | **Planned but not implemented** | D       | No model/router/page. |
| Recovery Test | **Planned but not implemented** | D       | No model/router/page. |
| SLO/SLA | **Deferred** | Later MSP/ITSM | Explicitly outside C1. |
| Incident workflow | **Deferred** | Later MSP/ITSM | Explicitly outside C1. |
| On-call/escalation | **Deferred** | C3/later MSP | No model or workflow. |


---

## 5.10 Application shell and UX

| Feature | Status | Release | Concrete evidence |
|---------|--------|---------|-------------------|
| Permission-aware navigation | **Implemented** | Foundation/UI | Implemented routes are grouped and inaccessible roadmap entries are filtered out. |
| Hidden unavailable roadmap links | **Implemented** | UI design | Tests confirm `available: false` entries are not rendered. |
| Visible “coming soon” links | **Abandoned** | UI supersession | Explicitly rejected. |
| Root session-aware redirect | **Implemented** | Foundation/UI | Authenticated users route to their permitted home. |
| Protected global shell | **Implemented** | Foundation/UI | Context, account identity and logout are global. |
| Changes filter/timeline polish | **Implemented** | UI refinement | Shared components and tests exist. |
| Asset Type quick filters | **Implemented** | UI refinement | Current Assets page uses scoped type selectors. |
| Knowledge Gap filters | **Implemented** | UI refinement | URL-backed compact filters exist. |
| Knowledge Gap compact cards | **Implemented** | UI refinement | Current component includes the requested structure. |
| Assertions responsive layout | **Implemented** | UI refinement | UI regressions are covered. |
| Completeness panel spacing | **Implemented** | UI refinement | Current UI contains the fix. |
| Login branding | **Implemented** | UI refinement | The supplied Atlas Impact lockup is shared by shell and login. |
| Standalone Profile sidebar item | **Abandoned** | UI supersession | Replaced by account menu; `/profile` remains reachable. |
| Runtime customer branding | **Deferred** | Future enterprise UX | No branding model/UI. |
| Browser and installed-app branding | **Implemented** | Branding follow-up | Supplied favicon, PWA icons, Apple touch icon, manifest, and metadata are wired through the web app. |


---

# 6. Planned but not implemented

These items are committed future work in current repository documentation.

## C2 — Shared graph and analysis foundations

* C2.1 typed nodes and edges with stable namespaced identity;
* current-valid, bounded, deterministic, cycle-safe structural projection;
* endpoint-by-endpoint authorization and non-disclosure;
* compatibility adapters for focused C1 graph routes;
* C2.2 dependency groups, redundancy, quorum, and failure effects; and
* C2.3 recursive analysis traversal, evidence paths, and qualified states.

The dedicated Impact Analysis route, outage simulation, blast radius, recovery
ordering, and business severity remain Release E, not C2.1.

## C3 — People, Teams and structured ownership

* Person;
* Team;
* Team Membership;
* Service Role Assignment;
* Business Owner assignments;
* Technical Custodian assignments;
* Support Group assignments;
* ownership history;
* escalation and responsibility views;
* Asset ownership support;
* `owner_exists` completeness rule.

## C4 — Formal Documentation and Knowledge Objects

* KnowledgeObject;
* Runbook;
* Decision;
* Assumption;
* reusable Exception;
* review and expiry;
* links to Services, Assets and Business Functions;
* usable documents navigation and pages.

## Release D — Backup and Recovery

* Backup Policy;
* Backup Job;
* Backup Run/Copy;
* Backup Repository;
* Recovery Plan;
* Recovery Steps;
* Recovery Tests;
* recovery confidence;
* coverage and recovery-gap reporting.

## Release E — Full Impact Analysis

* recursive blast-radius calculation;
* outage simulation;
* confidence/evidence paths;
* scoring and prioritisation;
* affected owners and recovery sequence;
* dedicated `/impact-analysis`.

## Production and security hardening

* SSO/OIDC/SAML;
* MFA;
* external append-only audit export;
* queue/worker identity;
* scheduled plugin runs;
* retries and job status;
* production scheduler/control plane.


---

# 7. Deferred

The following are explicitly postponed or excluded from the current MVP/C1:

* billing and commercial tenancy above an Atlas workspace;
* password recovery email;
* recovery codes;
* per-device sessions;
* break-glass account recovery;
* arbitrary per-record policy;
* delegated role administration;
* customer-specific reference taxonomies;
* cross-customer/cross-site relationships;
* uploaded icon/media library;
* icon proxying;
* runtime/customer-specific branding;
* avatar upload;
* plugins beyond Proxmox;
* production scheduler/queue controls;
* bulk reconciliation acceptance;
* automatic rollback of accepted discovery;
* automatic deletion of absent Assets;
* arbitrary executable completeness expressions;
* Asset ownership rules before C3;
* enterprise Business Function/process hierarchy;
* SLO/SLA, incident, catalog, on-call and ITSM workflows;
* AI-generated remediation;
* deep graph traversal and outage simulation in C1;
* automatic conversion of legacy Service Assets.


---

# 8. Abandoned or superseded

| Feature/design | Status rationale |
|----------------|------------------|
| Browser `localStorage` session tokens | Superseded by HttpOnly cookie sessions. |
| Split-origin default production design | Superseded by same-origin `/api`; split-origin remains dev compatibility. |
| Missing Knowledge as a Reconciliation queue | Superseded by dedicated Knowledge Gaps. |
| Generic Hierarchy/Relationships topology tabs | Superseded by Physical, Platform, Network/VLAN, Dependency and All Relationships lenses. |
| Standalone Profile sidebar navigation | Superseded by top-right account menu. |
| Visible placeholder roadmap navigation | Superseded by hiding unavailable routes. |
| Role-name-only/browser-only authorisation | Superseded by backend permission keys and scoped assignments. |
| Recurring environment-backed admin reset | Superseded by one-time bootstrap. |
| Treating gaps as Reconciliation Items | Superseded by dedicated KnowledgeGap records. |
| Hard-coded Asset/Relationship enums | Superseded by managed database records. |
| Automatic deletion of missing Assets | Explicitly rejected. |
| Automatic conversion of legacy Service Assets | Explicitly rejected for C1. |
| Generic graph database requirement | Rejected; PostgreSQL remains the system of record. |


---

# 9. Unknown items

The repository does not provide a clear implementation or product decision for:

* concrete Integration secret-store backend;
* safe CIDR-based network membership suggestions;
* community Proxmox LXC installer;
* Portainer deployment artefacts;
* formal open-source/commercial licence status;
* 0.1 release packaging status.


---

# 10. Repository audit priority assessment

The July review identified the following value gaps. The 30 August sequencing
decision deliberately selects manual-first C2.1 next; this section records
parallel and later opportunities rather than chronological priority.

## Parallel incomplete workstream: operational integrations

Atlas already has the hardest individual parts:

* Integration schema;
* Proxmox connection adapter;
* Proxmox discovery;
* normalisation;
* idempotent sync;
* Data Sources;
* Discovery Runs;
* reconciliation;
* Changes;
* generated Markdown component.

The missing value chain is:

`Configured Integration → secret-reference resolution → Test Connection → Run Now → queue/worker dispatch → Proxmox plugin → raw evidence → assertions/reconciliation → status/progress/errors → scheduled repeat runs`

Until this exists, Atlas’s main discovery experience remains simulation-driven.

### B2 — Operational Integrations and live discovery

Build:

1. Integration CRUD API and replace the mock integrations page.
2. Secret-reference provider interface.
3. Safe initial provider, such as environment/file-backed references.
4. Test Connection endpoint and UI.
5. Run Now endpoint.
6. Worker queue and job record.
7. Proxmox plugin invocation.
8. Run progress/status/error persistence.
9. Retry and cancellation contract.
10. Link operational runs to Data Source, Discovery Run, Evidence and Changes.
11. Add schedule support only after Run Now is reliable.

## Contained opportunity: expose generated Documentation

The generation component already works. The next increment is relatively contained:

1. Documents router.
2. Document list page.
3. Document detail/Markdown renderer.
4. Links from Assets and Discovery Runs.
5. Regenerate action.
6. Download/export.
7. Service Markdown generation after the Asset surface is stable.

This converts hidden technical capability into visible user value.

## Foundation hardening: complete Interface-first IP UX

Remove or de-emphasise direct `Asset.ip_address` from:

* Asset create/edit form;
* Asset list display;
* filtering and sorting.

Use primary interface information consistently, retaining the legacy field only as a
migration/read-compatibility mechanism.

## Selected next product foundation: C2.1 Shared Operational Graph

Build on existing focused graphs:

1. stable typed node and edge identity;
2. current-valid bounded structural projection;
3. depth, cycle, ordering, and truncation controls;
4. semantic direction independent from traversal/presentation direction;
5. endpoint-by-endpoint authorization and non-disclosure;
6. Asset, Service, and Business Function focus from accepted manual knowledge;
7. compatibility adapters for both focused C1 routes; and
8. no impact, outage, recovery, scoring, or change-safety conclusions.

## Later domain release: C3 structured ownership

Replace free-text labels with:

* Person;
* Team;
* membership;
* role assignments;
* history;
* ownership filters and escalation views.

Preserve and migrate C1 text values safely.

## Later domain release: Release D Backup and Recovery

Once live discovery and ownership are stable, add:

* Backup Policy;
* Repository;
* Job/Run/Copy;
* Recovery Plan/Step/Test;
* PBS adapter;
* recovery coverage and readiness.


---

# 11. Revised release plan

| Release | Scope | Actual status |
|---------|-------|---------------|
| **0.1 Platform Foundation** | Runtime, single-origin deployment, auth, RBAC, tenancy, inventory, networks, relationships, custom fields, topology | **Implemented** |
| **A Knowledge Foundation** | Evidence, assertions, provenance, accepted/current truth, history and Changes | **Implemented** |
| **B Discovery & Reconciliation — Simulation** | Data Sources, JSON simulation, runs, coverage, reconciliation and no-longer-observed | **Implemented** |
| **B2 Operational Integrations and live discovery** | Integration management, secret resolution, worker dispatch, Run Now, scheduling and live Proxmox runs | **Partially implemented; parallel operational-hardening stream** |
| **B.5 Knowledge Completeness** | Asset/Service requirements, gaps, defer/exception/assignment/resolve | **Implemented** |
| **C1 Homelab Service MVP** | Services, Service Types, Criticality, Business Functions, dependencies, ownership labels, RTO/RPO and focused graphs | **Implemented** |
| **C2.1 Shared Operational Graph** | Reusable API-owned structural graph projection and compatibility adapters | **Selected next increment; not implemented at audit point** |
| **C2.2 Dependency Semantics** | Redundancy, quorum, dependency groups, and failure effects | **Planned** |
| **C2.3 Analysis Primitives** | Recursive analysis traversal, explanation paths, states, and confidence qualification | **Planned** |
| **C3 MSP Ownership** | People, Teams, memberships and role assignments | **Planned**   |
| **C4 Knowledge Objects** | Runbooks, Decisions, Assumptions, Exceptions and Documentation UI | **Planned; generated Markdown foundation exists** |
| **D Backup & Recovery** | Protection, backup and recoverability model | **Planned**   |
| **E Full Impact Analysis** | Outage simulation, blast radius and explainable recovery readiness | **Planned**   |
| **F Intended State / broader knowledge outputs** | NetBox intended state, drift and mature documentation outputs | **Planned**   |


---

# 12. Approved forward sequence — 30 August 2026

The selected next development increment is **C2.1 — Shared Operational Graph**.
This choice implements the manual-first strategy. B2 remains incomplete but is
not a prerequisite or immediate sequencing gate.

## Increment 1 — C2.1 Shared Operational Graph

Create one secure, deterministic, API-owned structural graph projection over
accepted Assets, Services, Business Functions, and current relationship records.
Preserve the existing Service and Business Function graph contracts through
compatibility adapters.

## Parallel stream — B2 Operational Integrations and live discovery

Track Integration APIs, secret-reference resolution, Test Connection, Run Now,
worker dispatch, job status, retries, cancellation, scheduling, and live
Proxmox execution as a separate incomplete stream. Heavy investment is
deliberately postponed during the immediate manual-first period. This stream is
necessary before Atlas makes trustworthy live availability or freshness claims,
but it is outside C2.1.

## Increment 2 — C2.2 Dependency Semantics

Add explicit dependency groups, all/any/minimum behavior, quorum, redundancy,
and failure-effect semantics.

## Increment 3 — C2.3 Analysis Primitives

Add recursive analytical traversal, path explanation, direct/downstream
classification, impact states, uncertainty, and engine versioning.

## Subsequent product increments

- Begin C3 structured ownership and C4 formal Knowledge Objects once C2.1
  contracts stabilize.
- Deliver F1 Documentation independently when useful; it is not blocked by C2.
- Complete the Interface-first IP transition as a foundation-hardening item.
- Deliver E1 Explainable Failure Impact after C2.3.
- Deliver D1 Recovery Knowledge Readiness, then evidence-backed D2 recovery.
- Combine E3 and F2 for intended-state and planned-change simulation.
- Close the lifecycle through F3 post-change discovery and reconciliation.

The roadmap must continue to distinguish implemented status from selected
sequence. C2.1 is planned until the code, tests, and a new repository audit prove
otherwise.

---

# 13. Bottom-line assessment

Atlas is further advanced than a simple inventory MVP:

* the knowledge model is real;
* reconciliation is real;
* completeness is real;
* Services and Business Functions are real;
* graph projections are real;
* the Proxmox adapter and core sync are real;
* deterministic Markdown generation is real.

Connecting the implemented integration components into a usable live discovery
workflow remains a substantial incomplete journey. It is not the next required
release and is not a C2.1 blocker.

The selected next increment is **C2.1 — Shared Operational Graph** because Atlas
will first prove its knowledge and relationship model with manually curated
accepted data. B2 remains visible as a parallel incomplete workstream, and Atlas
must not present structural graph data as live operational proof.

C2.1 is successful when the repository has a reusable graph builder, a generic
focused graph API, compatibility adapters for the existing graph routes,
authorization and non-disclosure tests, and updated implementation evidence. It
is not successful merely because a new graph screen renders.
