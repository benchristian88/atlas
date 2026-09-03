# Atlas Product Feature Status Review

**Review basis:** Atlas AI-session transcripts in this project, the current conversation, the existing Atlas roadmap/navigation/architecture documents, and the user's explicit confirmation that **every item presented as a Codex implementation or fix prompt has been completed**.

**Review date:** 24 July 2026

> **Important evidence rule**
>
> This is a transcript-derived product audit, not a fresh source-code audit. “Implemented” means the transcript contains either an explicit report that the feature works, or a Codex implementation/fix prompt combined with the user’s final confirmation that every Codex prompt has been completed.
>
> Where the transcript only describes a target state, future phase, deferred design or architectural boundary, it is not classified as implemented.

---

# 1. Status definitions

| Status | Meaning used in this review |
|---|---|
| **Implemented** | Explicitly reported working, or included in a completed Codex implementation/fix prompt. |
| **Partially implemented** | A foundation, narrow slice, UI shell, simulation or limited implementation exists, but the described end-state is incomplete. |
| **Planned but not implemented** | Assigned to the roadmap or discussed as a future build, with no completed implementation prompt or success report. |
| **Deferred** | Explicitly postponed, excluded from the MVP/current release or reserved for a later enterprise/MSP phase. |
| **Abandoned** | Explicitly rejected as the chosen approach, superseded by another design or deliberately not pursued. |
| **Unknown** | Mentioned, but the transcripts do not establish whether it exists or works. |

---

# 2. Executive assessment

## Current release position

Atlas appears to have completed:

- the original platform/inventory foundation;
- **Release A — Knowledge Foundation**;
- most or all of the transcript-defined **Release B — Discovery Reconciliation foundation**;
- the added **Knowledge Completeness** capability that sits between Releases B and C;
- **Release C1 — Homelab Service MVP**;
- a substantial set of production-readiness, navigation and UI improvements.

Atlas has **not yet completed the full original Release C scope**. The delivered C1 slice deliberately reduced Release C to a homelab-appropriate service model.

The main remaining roadmap is therefore:

1. **Release B hardening against real integrations**, if current reconciliation remains primarily simulation/manual-run driven.
2. **Release C2/C3/C4 expansion**:
   - impact-oriented Service Graph refinement;
   - structured People and Teams;
   - ownership-role assignments and escalation;
   - first-class Runbooks, Decisions, Assumptions and Exceptions.
3. **Release D — Backup and Recovery Model**.
4. **Release E — Impact and Recovery Analysis**.
5. **Release F — Knowledge Outputs and NetBox intended state**.
6. Wider integration/plugin coverage and production/community distribution work.

## Status by formal roadmap release

| Release | Current classification | Evidence-based interpretation |
|---|---|---|
| Platform foundation / pre-A | **Implemented, with some operational limitations** | Authentication, RBAC, customer/site scoping, assets, relationships, networks, interfaces, custom fields, administration, Docker deployment and single-origin API were all described in completed prompts or reported working. |
| Release A — Knowledge Foundation | **Implemented** | Evidence Records, Knowledge Assertions, provenance, fact history, accepted/current distinction, declared manual edits, temporal history and Changes were all implemented through completed prompts. |
| Release B — Discovery Reconciliation | **Implemented at product-workflow level; partially proven for live integrations** | Reconciliation lifecycle, evidence staging, no-longer-observed/reobserved, contradiction handling and actions were implemented. The transcripts strongly evidence manual discovery simulation; they do not conclusively prove a full live Proxmox reconciliation cycle. |
| Knowledge Completeness Foundation | **Implemented** | Configurable requirements, Knowledge Gaps, evaluator, defer/exception actions, dedicated page and UI were implemented through completed prompts. |
| Release C1 — Homelab Service MVP | **Implemented** | The final C1 Codex prompt included Services, Service Types, Criticality, dependencies, Business Functions, RTO/RPO, simple ownership, service provenance, completeness, graph projection, navigation and UI. The user said it “seemed to work” and later confirmed all Codex prompts were completed. |
| Full Release C — Business and Service Graph | **Partially implemented** | C1 is complete, but Person, Team, structured ownership, escalation and formal knowledge objects were explicitly deferred. |
| Release D — Backup and Recovery | **Planned but not implemented** | Defined in the formal roadmap as the next recovery model; only lightweight Service recovery fields and links were included in C1. |
| Release E — Impact and Recovery Analysis | **Planned but not implemented** | Formal roadmap feature; C1 explicitly excluded full impact analysis. |
| Release F — Knowledge Outputs and Intended State | **Partially implemented foundation, major capability not implemented** | Documentation/worker boundaries exist, but explanatory deterministic documents and NetBox intended-state reconciliation remain future scope. |

---

# 3. Detailed feature inventory

## 3.1 Platform architecture, tenancy and security

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| PostgreSQL as durable system of record | **Implemented** | Foundation | Existing architecture states PostgreSQL stores users, inventory, managed reference data, discovery runs, generated documents and audit history. It remains the explicit source of truth throughout later prompts. |
| Next.js frontend | **Implemented** | Foundation | Repeated build, UI and navigation prompts refer to the live Next.js frontend. |
| FastAPI backend | **Implemented** | Foundation | Repeated API routes, logs and migration prompts refer to the live FastAPI API. |
| Redis/worker boundary | **Partially implemented** | Foundation | Architecture says Redis and a long-running worker container exist, but “current worker orchestration remains intentionally limited.” |
| Customer tenancy | **Implemented** | Foundation | Customer/site context, scoped authorization and customer selectors were implemented before the knowledge releases. |
| Site scoping | **Implemented** | Foundation | Assets, networks and relationships are customer/site scoped; later Service C1 requirements preserve this model. |
| Multi-customer MSP-compatible architecture | **Implemented as architecture/foundation** | Foundation | Architecture explicitly supports a single homelab and multi-customer MSP installation. Full MSP operational features remain future work. |
| Database-backed authentication | **Implemented** | Foundation | Login was tested and fixed; architecture documents session-version invalidation and protected routes. |
| HttpOnly cookie authentication | **Implemented** | Foundation | Architecture describes same-origin API JSON and HttpOnly cookie use; user fixed `cookie secure` configuration during deployment testing. |
| Role-based access control | **Implemented** | Foundation | Scoped RBAC, master/admin/customer/site/view roles and backend enforcement were part of completed implementation prompts. |
| Global/customer/site role assignments | **Implemented** | Foundation | Architecture and authentication documentation describe explicit permissions plus scoped role assignments. |
| Forced password change | **Implemented** | Foundation | Administration design includes temporary password and force-password-change handling; architecture describes enforcement. |
| User management | **Implemented** | Foundation | User APIs, active/disabled status, roles and access assignments were part of the administration implementation. |
| Profile display-name update | **Implemented** | Foundation/UI | Existing Profile page supported display-name changes; later moved behind the top-right user menu. |
| Profile password change | **Implemented** | Foundation/UI | Existing Profile page explicitly allowed password changes. |
| Personal accent/theme colour | **Implemented** | Foundation/UI | Existing Profile page allowed theme/accent changes; authentication documentation describes validated hex accent values. |
| Profile avatar upload | **Deferred** | Future account enhancement | User menu prompt explicitly said not to implement full avatar upload unless already supported; fallback initials were implemented and avatar support was prepared for later. |
| User avatar/initials component | **Implemented** | UI refinement | Completed user-menu prompt required a reusable avatar component with image URL support and initials fallback. |
| Top-right account dropdown | **Implemented** | UI refinement | Completed prompt moved Profile and Logout to a dropdown beside the user identity. |
| Bottom-left Profile navigation item | **Abandoned/removed** | UI refinement | Completed prompt explicitly removed the standalone Profile item and made the top-right account menu the single entry point. |
| Logout from account dropdown | **Implemented** | UI refinement | Included in the completed top-right user menu prompt. |
| SSO for Atlas login | **Planned but not implemented** | Future security | Deployment documentation says local authentication “does not yet provide SSO.” |
| MFA | **Planned but not implemented** | Future security | Deployment documentation explicitly says MFA is not yet provided. |
| Email-based account recovery | **Planned but not implemented** | Future security | Deployment documentation explicitly says this is not yet provided. |
| Break-glass recovery command | **Planned but not implemented** | Future security | Deployment documentation explicitly says this is not yet provided. |
| Active-session management | **Deferred** | Future account enhancement | Target Profile content describes “active sessions later.” |
| Audit log | **Implemented** | Foundation | Architecture and authentication documents describe durable read-only, permission-gated audit APIs. |
| Tamper-evident external audit retention | **Planned but not implemented** | Production hardening | Architecture says external append-only export is needed for tamper-evident retention. |
| Application-level distributed login throttling | **Planned but not implemented** | Production hardening | Deployment documentation recommends reverse-proxy rate limits “until distributed application throttling is available.” |

## 3.2 Deployment and portability

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Docker Compose deployment | **Implemented** | Foundation | User repeatedly built Atlas using `infra/docker/docker-compose.yml`; deployment documentation exists. |
| Environment-file based secrets/configuration | **Implemented** | Foundation | Builds use `--env-file .env`; missing `AUTH_SECRET_KEY` was diagnosed and fixed. |
| Single-origin production API under `/api/*` | **Implemented** | Production readiness | A full completed Codex prompt migrated FastAPI and frontend calls to same-origin `/api`. |
| Deployment-agnostic public hostname | **Implemented** | Production readiness | Single-origin prompt prohibited hard-coded Atlas domains and made relative `/api` the default. |
| Split-origin local development | **Implemented/preserved** | Production readiness | Single-origin prompt explicitly retained absolute API URL override for direct-port development. |
| CORS-free normal production browser traffic | **Implemented** | Production readiness | Same-origin migration was specifically designed to avoid production cross-origin requests. |
| Cloudflare independence | **Implemented** | Production readiness | Completed prompt required Cloudflare to remain optional and absent from application design. |
| Reverse-proxy independence | **Implemented** | Production readiness | Completed prompt required compatibility with Nginx Proxy Manager, Traefik, Caddy or another standards-compliant proxy. |
| Generic `/api/health` checks | **Implemented** | Production readiness | Included in the completed same-origin migration. |
| Secure-cookie deployment configuration | **Implemented/configurable** | Production readiness | User diagnosed login failure caused by secure cookies on HTTP; deployment supports correct secure/insecure configuration. |
| Documented upgrade and rollback process | **Implemented** | Production readiness | `deployment-and-upgrades.md` describes backups, schema/application matching and rollback. |
| Proxmox LXC community installer | **Planned but not implemented** | Pre-0.1/community release | Earlier product discussion identified a community Proxmox LXC installation script as release preparation. No completed prompt is evidenced in this transcript. |
| Portainer-friendly GitHub Compose deployment | **Planned but not implemented** | Pre-0.1/community release | Earlier discussion proposed a cleaned or alternate Compose file usable directly from GitHub/Portainer. No completion evidence appears here. |
| Removal of MVP wording for 0.1 | **Planned but not implemented** | Pre-0.1/community release | Earlier discussion proposed removing “MVP” mentions from code/docs/application before 0.1. No completion evidence appears here. |
| Formal 0.1 release packaging | **Planned but not implemented** | Pre-0.1/community release | Discussed as a production/community release goal; no explicit completion report. |
| Licence selection and repository licence file | **Unknown** | Project governance | “Why Atlas” noted no licence file at review time, and a later conversation asked about licensing. No final repository action is established here. |

## 3.3 Core inventory and administration

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Asset model | **Implemented** | Foundation | Assets are the core operational view throughout all prompts. |
| Asset list page | **Implemented** | Foundation/UI | Multiple completed prompts refined asset quick filters and typography. |
| Asset detail page | **Implemented** | Foundation | Knowledge history, assertions, completeness and relationships were added to it. |
| Manual asset creation/editing | **Implemented** | Foundation | Manual assets were already present; later prompts fixed provenance for manual edits. |
| Asset archive/delete safeguards | **Implemented** | Foundation | Existing administration and relationship rules use restrictive lifecycle handling; later discovery/assertion deletion prompts used safe archive/delete. |
| Database-defined Asset Types | **Implemented** | Foundation | User explicitly noted editable database asset types; administration and safe lifecycle are documented. |
| Asset Type active/inactive lifecycle | **Implemented** | Foundation | Referenced/system types cannot be deleted; deactivation is supported. |
| Asset Type icons | **Implemented** | Foundation | Default icon URL, asset override and safe fallback behavior are documented. |
| Existing Application Asset Type | **Implemented/retained** | Foundation/C1 | C1 explicitly preserved Application as a technical/deployed software Asset Type. |
| Existing Service Asset Type | **Implemented but conceptually superseded** | Foundation/C1 | C1 explicitly preserved it, warned of naming conflict, and did not migrate it automatically. |
| Automatic migration of existing Service Assets into first-class Services | **Abandoned for C1** | Release C1 | C1 prompt explicitly prohibited automatic migration or duplicate Service creation. |
| Relationship model for Asset-to-Asset edges | **Implemented** | Foundation | Editable Asset Relationships underpin topology and hosting links. |
| Database-defined Relationship Types | **Implemented** | Foundation | User repeatedly emphasized editable Relationship Types; administration and safe lifecycle exist. |
| Relationship endpoint applicability | **Implemented** | Release C1 | C1 completed prompt extended Relationship Types for Asset→Asset, Service→Asset, Service→Service and Service→Business Function applicability. |
| Asset Interfaces | **Implemented** | Foundation | Architecture and knowledge-history discussions include interfaces. |
| IP address data | **Implemented** | Foundation/Release A | IP is a high-value temporal fact and part of interfaces/networks. |
| Networks/VLANs | **Implemented** | Foundation | Current Atlas includes networks/VLANs; navigation retains Networks. |
| Customer/site-safe relationships | **Implemented** | Foundation | Authentication documentation says new Asset relationships require same authorized customer/site. |
| Custom fields | **Implemented** | Foundation | Typed custom field definitions, choices, applicability and values are documented. |
| Custom-field maximum per Asset Type | **Implemented** | Foundation | Documentation states a maximum of ten active rendered fields for any type. |
| Customers administration | **Implemented** | Foundation | Existing admin reference data includes Customers. |
| Sites administration | **Implemented** | Foundation | Existing admin reference data includes Sites. |
| User/role/permission administration | **Implemented** | Foundation | Architecture and navigation documents describe the working administration boundaries. |
| System settings | **Implemented** | Foundation | Redacted, global-permission-only settings are documented. |
| Administration landing page `/admin` | **Implemented** | UI refinement | Completed navigation prompt changed the System item from `/admin/system-settings` to `/admin`. |
| Safe referential deletion checks | **Implemented** | Foundation | Customer/site/reference records are deactivated or deletion-blocked when referenced. |
| Search Atlas global search | **Unknown** | Future/UI | Screenshot showed a top-bar “Search Atlas…” control, but no transcript evidence establishes full global-search behavior. |

## 3.4 Knowledge Graph and topology

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Infrastructure topology | **Implemented** | Foundation | Existing topology was renamed/presented as Knowledge Graph. |
| Knowledge Graph page | **Implemented** | Foundation | Multiple UI prompts reference its working controls and style. |
| Asset relationship graph | **Implemented** | Foundation | Existing relationships drive topology/Knowledge Graph. |
| Customer/site-scoped graph | **Implemented** | Foundation | Architecture and C1 requirements preserve scoped graph access. |
| Service nodes in graph | **Implemented** | Release C1 | C1 completed prompt added basic Service graph projection and distinct Service nodes. |
| Business Function nodes in graph | **Implemented** | Release C1 | C1 completed prompt added Business Function→Service→Asset traversal. |
| Service-focused graph endpoint | **Implemented** | Release C1 | C1 specified `GET /services/{id}/graph`. |
| Upstream and downstream Service dependencies | **Implemented** | Release C1 | Service detail and graph requirements included “Depends on” and “Required by.” |
| Graph node links to detail pages | **Implemented** | Release C1 | C1 graph requirements included clickable entity nodes. |
| Graph filters for business/services/infrastructure | **Implemented** | Release C1 | C1 required node-type filters for Business context, Services and Infrastructure. |
| Provenance displayed directly on graph edges | **Planned but not implemented** | Later graph maturity | Target navigation says the graph should eventually support provenance, temporal facts, confidence and freshness. |
| Temporal graph/time-travel view | **Planned but not implemented** | Later graph maturity | Target graph “eventually” supports temporal facts; no completed feature prompt for a point-in-time graph. |
| Intended-state graph view | **Planned but not implemented** | Release F | Navigation lists Intended State and Observed State as future graph views. |
| Ownership graph view | **Deferred** | Release C3 | People/Teams and structured ownership were explicitly deferred from C1. |
| Recovery graph view | **Planned but not implemented** | Release D/E | Target Knowledge Graph includes Recovery, dependent on structured recovery objects. |
| Full impact paths in graph | **Planned but not implemented** | Release E | C1 explicitly said not to build full impact analysis. |
| Neo4j/graph database | **Abandoned** | Architecture decision | Roadmap and “Why Atlas” explicitly say PostgreSQL is sufficient and a graph database is not required. |

## 3.5 Release A — Knowledge Foundation

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| EvidenceRecord | **Implemented** | A | Project transcript says EvidenceRecord→KnowledgeAssertion→ReconciliationItem is the core flow. |
| KnowledgeAssertion | **Implemented** | A | Assertions page, assertion status fixes and history were repeatedly tested and refined. |
| EntitySourceLink | **Implemented** | A | Project transcript identifies it as mapping source identities to Atlas entities. |
| Truth classifications | **Implemented** | A | Architecture includes Observed, Declared, Intended and Inferred classifications. |
| Observed assertions | **Implemented** | A | Discovery simulation creates observed assertions. |
| Declared assertions | **Implemented** | A | Manual edits were changed to create declared, accepted assertions. |
| Intended assertions | **Implemented as model capability; usage limited** | A/F | Truth classification exists, but NetBox intended-state ingestion remains future Release F. |
| Inferred assertions | **Implemented as classification/framework; broader inference limited** | A/B/E | Reconciliation includes inferred categories, but broad automated inference is not proven. |
| First/last observed dates | **Implemented** | A | Required by Release A and used by no-longer-observed/reobserved workflows. |
| Valid-from/valid-to temporal facts | **Implemented** | A | Release A scope and history model include temporal validity. |
| Confidence | **Implemented as assertion metadata** | A | Release A includes confidence; no evidence of advanced confidence computation. |
| Confirmation status | **Implemented** | A | Release A completion test includes human confirmation state. |
| Supersession | **Implemented** | A | Current vs accepted prompt implemented superseding prior accepted single-valued assertions. |
| Current source observation vs accepted canonical truth | **Implemented** | A hardening | Completed prompt introduced `is_source_current` versus `is_accepted`. |
| Single accepted value for single-valued predicates | **Implemented** | A hardening | Completed prompt enforced one accepted canonical assertion while allowing multiple source-current observations. |
| Asset fact history | **Implemented** | A | Project transcript explicitly says asset fact history was implemented. |
| Knowledge History UI | **Implemented** | A/UI | Current/accepted display was corrected; summary/history/raw views were designed and implemented. |
| Raw Assertions view | **Implemented** | A/UI | Completed prompt retained raw assertions, grouped/collapsed by predicate. |
| Conflict display | **Implemented** | A/UI | Completed prompt required incompatible current assertions to be shown as conflicts. |
| Manual Asset edits in knowledge history | **Implemented** | A hardening | Completed prompt fixed manual edits not appearing in history. |
| Assertion retract/delete | **Implemented** | A | Earlier completed prompt added safe retract/delete actions. |
| Assertions table overflow fix | **Implemented** | UI fix | Project transcript says overflow was addressed. |
| JSON-safe assertion serialization | **Implemented** | A hardening | C1 and prior fixes required shared JSON-safe normalization and avoiding optional-reference 500s. |
| Provenance panel on assets | **Implemented** | A | Project transcript describes provenance/knowledge history on Asset detail. |
| Full provenance panel on every relationship type | **Unknown** | A extension | Roadmap targeted selected facts and relationships; transcript does not prove complete coverage for all relationship types. |
| Human knowledge review/reconfirmation workflow | **Planned but not fully implemented** | Cross-cutting future | Roadmap says human-entered knowledge should have review/reconfirmation rather than remaining permanently trusted. Some gap/defer workflows exist, but no complete reconfirmation cycle is evidenced. |

## 3.6 Release B — Discovery and Reconciliation

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Discovery Run lifecycle | **Implemented** | B | Project transcript explicitly says discovery run lifecycle was implemented. |
| Manual discovery simulation | **Implemented** | B test harness | Baseline, complete, partial and re-observation payloads were used and debugged. |
| Discovery-run archive/delete | **Implemented** | B | Safe archive/delete was added through a completed prompt. |
| RunObservedEntity | **Implemented** | B | Null UUID defect was fixed through a completed migration prompt. |
| Complete snapshot coverage keys | **Implemented** | B | Project transcript says coverage keys and complete snapshots were added. |
| Partial snapshot protection | **Implemented** | B | Test rule explicitly says partial runs must not create missing/no-longer-observed items. |
| No-longer-observed detection | **Implemented** | B | Baseline/second-run simulation created no-longer-observed for omitted entities. |
| Re-observed detection | **Implemented** | B | Third run restored the entity and recorded reobserved. |
| Cross-coverage isolation | **Implemented** | B | Different coverage keys were required not to cross-compare. |
| Reconciliation inbox/page | **Implemented** | B | Current system has dedicated Reconciliation navigation and queues. |
| New item queue | **Implemented** | B | Release B and current reconciliation categories include newly discovered. |
| Changed item queue | **Implemented** | B | Implemented Changes/Reconciliation logic handles changed facts. |
| No Longer Observed queue | **Implemented** | B | Explicitly simulated and implemented. |
| Contradictions queue | **Implemented** | B | Current vs accepted conflicts and reconciliation categories include contradictions. |
| Possible duplicates queue | **Partially implemented/unknown** | B | Target navigation includes it, but current transcript does not clearly show duplicate matching workflow completion. |
| Inferred relationships queue | **Partially implemented/unknown** | B | Included in target queues; no explicit end-to-end test in the transcript. |
| Stale human knowledge queue | **Planned but not clearly implemented** | B/Cross-cutting | Mentioned in target navigation; no completed prompt explicitly focused on reconfirmation/stale human knowledge. |
| Accept action | **Implemented** | B | Reconciliation accepts proposed knowledge into operational view. |
| Reject action | **Implemented** | B | Release B actions and existing reconciliation implementation include rejection. |
| Confirm action | **Implemented/likely** | B | Included in implemented workflow design; exact UI test not independently reported. |
| Merge action | **Partially implemented/unknown** | B | Target action exists, but transcript does not conclusively show entity-merge functionality. |
| Retain declared value | **Implemented/likely** | B | Part of completed reconciliation prompt architecture and precedence handling. |
| Accept observed value | **Implemented/likely** | B | Part of completed reconciliation workflow. |
| Record exception | **Implemented** | B/Knowledge Gaps | Visible Knowledge Gap cards include Record exception; reconciliation target also uses exceptions. |
| Defer | **Implemented** | B/Knowledge Gaps | Visible UI and completed prompt include defer. |
| Reclassify | **Unknown** | B | Target action is documented, but no explicit completed implementation is shown. |
| Add explanation | **Unknown** | B | Target action documented; no direct evidence of a working explanation field/action. |
| Operator decision history | **Implemented** | B | Release B key deliverable and knowledge changes/history were included in completed prompts. |
| Source precedence framework | **Implemented at foundation level** | B | Current vs accepted and “retain declared/accept observed” logic indicate precedence support. Extent of per-field configurability is uncertain. |
| Real Proxmox discovery feeding reconciliation | **Partially implemented/unknown** | B | Architecture documents a Proxmox plugin, but transcript testing focused strongly on manual discovery simulation. |
| Scheduled discovery | **Planned but not implemented** | Integrations/B | Target navigation includes schedules; architecture says worker orchestration remains intentionally limited. |
| Discovery error/results/coverage views | **Partially implemented** | B | Discovery run lifecycle and coverage exist, but the full target tab set is not proven. |
| Discovery must not silently overwrite accepted knowledge | **Implemented as architectural rule** | B | Core model and completion tests explicitly enforce staged reconciliation. |

## 3.7 Knowledge Changes and timeline

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Meaningful Changes timeline | **Implemented** | A/B | Project transcript explicitly says meaningful Changes timeline was implemented. |
| Changes separate from Audit Log | **Implemented conceptually and in UI** | A/B | Navigation states Changes explains knowledge changes; Audit records security/admin activity. |
| Asset-created/changed events | **Implemented** | A/B | Changes includes meaningful asset and fact changes. |
| Relationship change events | **Implemented** | A/B/C1 | Asset and Service dependency add/remove actions create Knowledge Changes. |
| No-longer-observed events | **Implemented** | B | Explicitly part of the simulation lifecycle. |
| Re-observed events | **Implemented** | B | Explicitly recorded in the third-run test. |
| Human edit events | **Implemented** | A | Manual edits create assertions and meaningful Knowledge Changes. |
| Service events on Changes | **Implemented** | C1 | C1 required Service events and entity filtering. |
| Compact date-grouped timeline | **Implemented** | UI refinement | Completed UI prompt aligned Changes with the Asset History Timeline. |
| Changes filter toolbar | **Implemented** | UI refinement | Completed prompt made controls compact and consistent with Knowledge Graph. |
| Active filter/query-string behavior | **Implemented** | UI refinement | Completed prompt required URL state, reset behavior and routing safety. |
| Alerts page based on attention-worthy changes/gaps | **Planned but not implemented** | Future Overview | Full target navigation includes Alerts; no completed implementation prompt. |

## 3.8 Knowledge Completeness and Knowledge Gaps

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| KnowledgeRequirementDefinition | **Implemented** | B→C foundation | Completed prompt added database-configured requirements. |
| KnowledgeGap object | **Implemented** | B→C foundation | Dedicated Knowledge Gaps page and cards exist in screenshots. |
| Separation of Reconciliation and Knowledge Gaps | **Implemented** | B→C foundation | Completed navigation prompt moved Missing Knowledge into its own `/knowledge-gaps` route. |
| Requirement rules tied to editable Asset Types | **Implemented** | B→C foundation | User emphasized database-defined types; completed prompt forbade hard-coded type names. |
| Requirement rules tied to editable Relationship Types | **Implemented** | B→C foundation | Completed prompt referenced database-defined Relationship Type IDs. |
| Requirement rules tied to Custom Fields | **Implemented** | B→C foundation | Completed prompt referenced Custom Field IDs. |
| Field-present rule | **Implemented** | B→C foundation | Included in the completed completeness design. |
| Interface-exists rule | **Implemented** | B→C foundation | Included in the completed completeness design. |
| Interface-has-IP rule | **Implemented** | B→C foundation | Included in the completed completeness design. |
| Relationship-exists rule | **Implemented** | B→C foundation | Included in the completed completeness design. |
| Relationship target-type rule | **Implemented** | B→C foundation | Included in the completed completeness design. |
| One-of rule | **Implemented** | B→C foundation | Included in the completed completeness design and reused in C1. |
| Unless/conditional rule | **Implemented** | B→C foundation | Included in the completed completeness design. |
| Freshness rule | **Implemented/likely** | B→C foundation | Included in completed completeness prompt; exact UI behavior not independently shown. |
| Required/conditional/recommended levels | **Implemented** | B→C foundation | Visible gap card shows Required; prompt required all levels. |
| Severity | **Implemented** | B→C foundation | Visible card shows Medium; filtering prompt includes severity. |
| Gap assignment | **Implemented/likely** | B→C foundation | Original completeness prompt included assign; filter prompt includes assigned user. Exact use is not shown. |
| Gap defer | **Implemented** | B→C foundation | Visible action button. |
| Gap exception | **Implemented** | B→C foundation | Visible Record exception action. |
| Gap reopen after data removal | **Implemented** | B→C/C1 | Completeness evaluator was required to reopen gaps when facts/dependencies are removed. |
| Idempotent evaluator | **Implemented** | B→C foundation | Completed prompt required no duplicate open gaps. |
| Evaluation after Asset changes | **Implemented** | B→C foundation | Completed prompt required evaluation after asset/interface/relationship changes. |
| Evaluation after Service changes | **Implemented** | C1 | C1 extended the same engine to Services. |
| Asset completeness panel | **Implemented** | B→C foundation | Screenshot and padding fix confirm it exists. |
| Service completeness panel | **Implemented** | C1 | C1 required completeness on Service detail. |
| Dedicated `/knowledge-gaps` page | **Implemented** | B→C foundation | Completed navigation and route fix. |
| Knowledge Gap search/filter toolbar | **Implemented** | UI refinement | Completed prompt matched Changes filter style. |
| Entity Type filter: Asset vs Service | **Implemented** | C1 | C1 required Service gaps on `/knowledge-gaps`. |
| Compact redesigned Knowledge Gap card | **Implemented** | UI refinement | Completed prompt restructured card around asset/service, missing information, dates, next step and left-aligned actions. |
| “Provide information” action | **Implemented** | B→C foundation | Visible action on current card. |
| “Open asset/service” action | **Implemented** | B→C/C1 | Visible Open asset; C1 required links to Service. |
| Recovery-specific gap types | **Partially implemented** | C1/D | Service recovery fields/gaps exist; full backup/recovery gap model belongs to Release D. |
| Organisation-wide alerts generated from gaps | **Planned but not implemented** | Future Overview | Alerts page is future target state. |

## 3.9 Release C1 — Homelab Service MVP

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| First-class Service model | **Implemented** | C1 | Completed C1 prompt; user said it worked. |
| `/services` index | **Implemented** | C1 | Included in completed C1 prompt. |
| Service create flow | **Implemented** | C1 | Included in completed C1 prompt and user discussed creating DNS. |
| Service edit flow | **Implemented** | C1 | Included in completed C1 prompt. |
| Service detail page | **Implemented** | C1 | Included in completed C1 prompt. |
| Service archive/restore | **Implemented** | C1 | Included in completed C1 API scope. |
| Database-defined Service Types | **Implemented** | C1 | Completed prompt added editable ServiceType records and admin management. |
| Starter Service Types | **Implemented** | C1 | Prompt seeded application, infrastructure, platform, shared, external, database, integration and business services. |
| Database-defined Criticality Levels | **Implemented** | C1 | Completed prompt added editable CriticalityLevel records. |
| Starter Criticality levels | **Implemented** | C1 | Prompt seeded Critical/High/Medium/Low. |
| Criticality rank | **Implemented** | C1 | Included for sorting and future impact calculations. |
| Default RTO/RPO recommendations by criticality | **Implemented** | C1 | Prompt required suggestions without overwriting explicit values. |
| Service purpose | **Implemented** | C1 | Core required/strongly recommended field. |
| Service description | **Implemented** | C1 | Included in model/UI. |
| Lifecycle status | **Implemented** | C1 | Included in model/UI. |
| Operational status | **Implemented** | C1 | Included as optional field. |
| Simple owner field | **Implemented** | C1 | `owner_name` implemented instead of Person/Team model. |
| Simple technical contact | **Implemented** | C1 | Implemented as plain field. |
| Simple support group | **Implemented** | C1 | Implemented as plain field. |
| RTO stored in minutes | **Implemented** | C1 | Prompt specified minute storage and human-friendly UI. |
| RPO stored in minutes | **Implemented** | C1 | Prompt specified minute storage and human-friendly UI. |
| Recovery notes | **Implemented** | C1 | Included in model/detail/completeness. |
| Runbook URL | **Implemented** | C1 | Lightweight link implemented instead of formal Runbook object. |
| Documentation URL | **Implemented** | C1 | Included in model/UI. |
| Service→Asset dependency | **Implemented** | C1 | Typed ServiceAssetDependency model and UI were in completed prompt. |
| Service→Application Asset relationship | **Implemented through generic Service→Asset dependency** | C1 | Relationship Types such as PROVIDED_BY can point Service to the existing Application Asset. |
| Service→LXC/VM direct dependency | **Implemented** | C1 | C1 deliberately allows direct dependency without requiring Application Asset. |
| Required-for-operation flag | **Implemented** | C1 | Included in Service→Asset and Service→Service dependency models. |
| Service→Service dependency | **Implemented** | C1 | Typed ServiceDependency model and “Depends on/Required by” UI included. |
| Self-reference prevention | **Implemented** | C1 | Explicit C1 constraint. |
| Legitimate dependency cycles | **Implemented/allowed** | C1 | Prompt prohibited blanket cycle rejection. |
| Lightweight Business Function model | **Implemented** | C1 | Included in completed prompt. |
| `/business-functions` index | **Implemented** | C1 | Included in completed prompt. |
| Business Function detail page | **Implemented** | C1 | Included in completed prompt. |
| Service→Business Function linkage | **Implemented** | C1 | Typed ServiceBusinessFunction model included. |
| Primary Business Function flag | **Implemented** | C1 | Included in linkage model. |
| Service provenance/assertions | **Implemented** | C1 | Manual Service edits create declared accepted assertions. |
| Service Knowledge Changes | **Implemented** | C1 | Service create/update/dependency/criticality/owner/recovery events added. |
| Service Knowledge Gaps | **Implemented** | C1 | Completeness engine extended with `entity_type=service`. |
| High/Critical conditional Service requirements | **Implemented** | C1 | RTO, RPO, owner/contact and recovery notes/runbook required conditionally. |
| External-Service exception for local Asset dependency | **Implemented** | C1 | C1 included profile/exception behavior for external Services. |
| Service summary/dashboard metrics | **Implemented** | C1 | Completed prompt required total, critical, missing-recovery and incomplete counts. |
| Services navigation item | **Implemented** | C1 | Added under Knowledge. |
| Business Functions navigation item | **Implemented** | C1 | Added under Knowledge. |
| Service graph projection | **Implemented** | C1 | Basic traversal and graph endpoint included. |
| Full impact analysis | **Deferred** | Release E | C1 explicitly said not to build it. |
| Automatic Service discovery from Application Assets | **Deferred/unknown** | Later integration work | C1 prohibited automatic migration/duplication; no later discovery workflow is evidenced. |
| “Application” as a separate first-class business object | **Abandoned for current model** | C1 design decision | The design chose one first-class Service model plus existing Application Asset Type, rather than separate Service and Application business models. |

## 3.10 Full Release C features beyond C1

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Person model | **Deferred** | C3 | C1 explicitly excluded a full Person model. |
| Team model | **Deferred** | C3 | C1 explicitly excluded a full Team model. |
| Team Membership | **Deferred** | C3 | C1 explicitly excluded Team Membership. |
| Structured ServiceRoleAssignment | **Deferred** | C3 | Replaced in C1 by simple owner/contact/support text fields. |
| Business Owner as structured Person/Team assignment | **Deferred** | C3 | C1 uses `owner_name`; migration path documented for later. |
| Technical Custodian as structured Person/Team assignment | **Deferred** | C3 | C1 uses `technical_contact`. |
| Support Group as structured Team assignment | **Deferred** | C3 | C1 uses plain `support_group`. |
| Multiple ownership assignments | **Deferred** | C3 | Not part of simple C1 fields. |
| Primary/secondary ownership | **Deferred** | C3 | Future structured role assignment design. |
| Ownership assignment history | **Deferred** | C3 | Explicitly excluded from C1. |
| Ownership dashboard/views | **Deferred** | C3 | Full Release C target includes ownership views; C1 relied on Service fields and filters. |
| Escalation contacts | **Deferred** | C3 | C1 explicitly excluded escalation schedules/advanced ownership. |
| Escalation paths | **Deferred** | C3 | Full navigation target links People/Teams to escalation paths; not in C1. |
| On-call rosters | **Deferred** | Future MSP/operations | Explicitly excluded from C1. |
| Support schedules | **Deferred** | Future MSP/operations | Explicitly excluded from C1. |
| First-class Runbook object | **Deferred** | C4/D/F | C1 implemented only a URL and recovery notes. |
| First-class Decision object | **Deferred** | C4 | Explicitly excluded from C1. |
| First-class Assumption object | **Deferred** | C4 | Explicitly excluded from C1. |
| First-class Exception knowledge object | **Deferred** | C4 | Gap exceptions exist, but formal linked Exception objects were excluded from C1. |
| Generic KnowledgeObject model | **Deferred** | C4 | Discussed as the later way to model Decision/Assumption/Exception/Runbook. |
| KnowledgeObjectLink | **Deferred** | C4 | Discussed for later documentation links. |
| Review/expiry workflow for knowledge objects | **Deferred** | C4 | Explicitly not part of MVP. |
| Full rich runbook authoring | **Deferred** | C4/F | Explicitly excluded from C1. |
| People & Teams navigation | **Deferred** | C3 | C1 explicitly said not to add People or Teams navigation. |
| HR/identity-system replacement | **Abandoned/not intended** | Product boundary | Target navigation explicitly says People/Teams are not intended to replace HR or identity management. |
| Generic polymorphic EntityRelationship table | **Abandoned for Release C** | Architecture decision | Discussion recommended typed ServiceAssetDependency, ServiceDependency, ServiceBusinessFunction and role tables instead, to preserve referential integrity. |
| Full enterprise Service taxonomy at C1 | **Abandoned for current release** | Scope decision | User and assistant explicitly reduced Release C to a homelab-appropriate vertical slice. |

## 3.11 Release D — Backup and Recovery

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Lightweight Service RTO | **Implemented** | C1 precursor | Service-level RTO implemented in C1. |
| Lightweight Service RPO | **Implemented** | C1 precursor | Service-level RPO implemented in C1. |
| Service recovery notes | **Implemented** | C1 precursor | Implemented in C1. |
| Runbook URL | **Implemented** | C1 precursor | Implemented as a lightweight link. |
| Backup relationship via existing Asset/Service Relationship Types | **Implemented at graph-link level** | C1 precursor | Example uses BACKED_UP_BY to PBS; this is not a structured backup model. |
| Backup Policy object | **Planned but not implemented** | D | Formal Release D scope. |
| Backup Job object | **Planned but not implemented** | D | Formal Release D scope. |
| Backup Copy object | **Planned but not implemented** | D | Formal Release D scope. |
| Backup Repository object | **Planned but not implemented** | D | Formal Release D scope. PBS may currently exist as an Asset, but not as a first-class structured repository object. |
| Recovery Plan object | **Planned but not implemented** | D | Formal Release D scope. |
| Recovery Step object | **Planned but not implemented** | D | Formal Release D scope. |
| Ordered recovery-plan editor | **Planned but not implemented** | D | Formal Release D key deliverable. |
| Recovery Test object | **Planned but not implemented** | D | Formal Release D scope. |
| Last successful backup evidence | **Planned but not implemented** | D | Formal Release D target content. |
| Last recovery test date/result | **Planned but not implemented** | D | Formal Release D target content. |
| Recovery confidence | **Planned but not implemented** | D | Formal Release D target content. |
| Recovery prerequisites | **Planned but not implemented** | D | Formal Release D scope. |
| Credential/secret references without secret storage | **Planned but not implemented** | D | Formal Release D scope. |
| Protection & Recovery section on Asset pages | **Planned but not implemented** | D | Formal key deliverable. |
| Protection & Recovery section on Service pages | **Partially implemented** | C1/D | C1 Recovery fields exist; full protection model does not. |
| Backup coverage reporting | **Planned but not implemented** | D | Formal key deliverable. |
| Critical-Service recovery gap reporting | **Partially implemented** | C1/D | Service RTO/RPO/runbook gaps exist; full backup coverage/recovery-plan gap reporting does not. |
| PBS integration enriching backup evidence | **Planned but not implemented/unknown** | D/Integrations | PBS was a target plugin and Asset dependency example; no structured backup discovery is proven. |
| Veeam integration | **Planned but not implemented** | Future integrations/D | Listed in target integrations. |

## 3.12 Release E — Impact and Recovery Analysis

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Basic dependency traversal | **Implemented** | C1 precursor | Service graph can traverse Business Function→Service→Service→Asset. |
| Cycle-aware Service graph design | **Implemented at dependency-model level** | C1 precursor | Cycles are allowed; full bounded traversal controls belong to E. |
| “What depends on this?” views | **Implemented in basic Service directionality** | C1 precursor | Service detail shows Depends on and Required by. |
| “What happens if this disappears?” action | **Planned but not implemented** | E | Formal Release E key deliverable. |
| Simulate failure | **Planned but not implemented** | E | “Why Atlas” proposes selecting a node and choosing Simulate failure. |
| Blast-radius view | **Planned but not implemented** | E | Formal Release E key deliverable. |
| Direct versus downstream impact | **Planned but not implemented** | E | Formal Release E scope. |
| Uncertain impact | **Planned but not implemented** | E | Formal Release E scope. |
| Contradiction-aware impact | **Planned but not implemented** | E | Formal Release E scope. |
| Evidence path explaining each result | **Planned but not implemented** | E | Formal Release E scope. |
| Depth limits | **Planned but not implemented** | E | Cross-cutting graph-performance requirement. |
| Cycle detection in impact traversal | **Planned but not implemented** | E | Formal Release E and cross-cutting requirement. |
| Bounded result sets/indexing | **Planned but not implemented** | E | Cross-cutting graph-performance requirement. |
| Affected Services from failed Asset | **Planned but not implemented** | E | Core blast-radius outcome. |
| Affected Business Functions | **Planned but not implemented** | E | Core blast-radius outcome. |
| Affected owners/custodians | **Deferred until structured ownership, then planned** | C3/E | C1 simple fields exist; full structured impact ownership depends on C3. |
| Recovery sequence output | **Planned but not implemented** | D/E | Requires Recovery Plan/Steps. |
| Recovery-readiness score/status | **Planned but not implemented** | E | Formal key deliverable; must be based on structured gaps rather than opaque AI judgment. |
| AI-generated opaque risk score | **Abandoned/not intended** | Product principle | Roadmap explicitly requires structured, explainable readiness instead of opaque AI judgement. |

## 3.13 Release F — Knowledge Outputs and Intended State

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Documentation data boundary/storage | **Partially implemented** | Foundation/F precursor | Architecture says PostgreSQL stores generated documents and worker boundary exists for generation. |
| Deterministic Asset documents | **Planned but not implemented/unknown** | F | Formal Release F scope; alpha vision mentions generated Asset documentation, but current functionality is not established. |
| Deterministic Service documents | **Planned but not implemented** | F | Formal Release F scope. |
| Site architecture documents | **Planned but not implemented** | F | Formal Release F and target navigation. |
| Recovery documents | **Planned but not implemented** | F | Requires Release D. |
| Impact reports | **Planned but not implemented** | F | Requires Release E. |
| Explanatory Markdown exports | **Planned but not implemented** | F | Formal Release F key deliverable. |
| Exportable documentation templates | **Planned but not implemented** | F | Formal Release F key deliverable. |
| Source references in generated docs | **Planned but not implemented** | F | Formal Release F key deliverable. |
| Evidence freshness indicators in docs | **Planned but not implemented** | F | Formal Release F key deliverable. |
| Risks and unresolved questions in docs | **Planned but not implemented** | F | Target documents must include these. |
| Always-current operations handbook | **Planned but not implemented** | F/product wedge | “Why Atlas” defines this as the desired product outcome. |
| DR pack export | **Planned but not implemented** | D/F | “Why Atlas” demo includes exporting a complete DR pack. |
| NetBox connector | **Planned but not implemented** | F | Formal Release F scope. |
| NetBox as Intended-state source | **Planned but not implemented** | F | Formal architecture principle. |
| NetBox silently defining Atlas truth | **Abandoned/not intended** | Architecture decision | NetBox is explicitly optional and must reconcile rather than overwrite Atlas. |
| Generated text inventing unsupported operational claims | **Abandoned/prohibited** | Cross-cutting | Roadmap requires generated text to be grounded in structured facts. |
| AI-model lock-in | **Abandoned/not intended** | Long-term architecture | Alpha vision says Atlas should expose structured context through open interfaces rather than embed a specific AI model. |
| AI assistant/Q&A over Atlas | **Planned but not implemented** | Post-F/AI layer | Alpha vision describes future AI questions such as “What changed this week?” and “Generate a disaster recovery plan.” |

## 3.14 Integrations and plugin ecosystem

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Plugin SDK boundary | **Implemented as foundation** | Foundation | Architecture describes vendor plugins normalizing data while core owns identity, tenancy and persistence. |
| Proxmox plugin | **Partially implemented** | Foundation/B | Architecture describes a read-only HTTPS API-token plugin. Full live reconciliation coverage is not conclusively established. |
| Proxmox connection validation | **Implemented/likely** | Foundation | Architecture says plugins validate connections and do not leak secrets. |
| Read-only Proxmox API token | **Implemented as design/security requirement** | Foundation | Explicit architecture requirement. |
| TLS verification by default | **Implemented as design/security requirement** | Foundation | Explicit architecture requirement. |
| Scheduled Proxmox discovery | **Planned but not implemented** | Integration hardening | Worker orchestration is intentionally limited. |
| Proxmox Backup Server plugin | **Planned but not implemented/unknown** | D/integrations | Listed as a target integration; no end-to-end implementation evidence. |
| Docker plugin/discovery | **Planned but not implemented/unknown** | Integrations | Listed in product vision and wedge; no definitive implementation report in this transcript. |
| UniFi plugin | **Planned but not implemented** | Future integrations | Listed as target plugin. |
| Fortinet plugin | **Planned but not implemented** | Future MSP integrations | Explicitly discussed as future plugin category. |
| Check Point plugin | **Planned but not implemented** | Future MSP integrations | Explicitly discussed as future plugin category. |
| Meraki plugin | **Planned but not implemented** | Future MSP integrations | Explicitly discussed as future plugin category. |
| VMware plugin | **Planned but not implemented** | Future integrations | Listed in target navigation. |
| Hyper-V plugin | **Planned but not implemented** | Future integrations | Listed in target navigation. |
| Veeam plugin | **Planned but not implemented** | Future integrations/D | Listed in target navigation. |
| Home Assistant plugin | **Planned but not implemented** | Future integrations | Listed in alpha vision. |
| GitHub plugin | **Planned but not implemented** | Future integrations | Listed in alpha vision. |
| Authentik plugin | **Planned but not implemented** | Future integrations | Listed in alpha vision. |
| Grafana plugin | **Planned but not implemented** | Future integrations | Listed in alpha vision. |
| Wazuh plugin | **Planned but not implemented** | Future integrations | Listed in alpha vision. |
| Nginx Proxy Manager plugin | **Planned but not implemented** | Future integrations | Listed in alpha vision. |
| n8n plugin | **Planned but not implemented** | Future integrations | Listed in alpha vision. |
| ITSM connectors | **Planned but not implemented** | Future MSP integrations | Target integration categories include ITSM. |
| Imported-file Data Source | **Planned but not implemented/unknown** | Connections | Target Data Sources include Imported File; current implementation is not established. |
| API Data Source | **Planned but not implemented/unknown** | Connections | Target Data Sources include API; public ingest capability is not established. |
| Data Source trust/precedence management | **Partially implemented** | A/B | DataSource records and source precedence concepts exist; full admin control is not conclusively shown. |
| Integration health/log views | **Planned but not implemented/unknown** | Connections | Target tabs include Health, Permissions and Logs. |
| Installed/Available integration marketplace UI | **Planned but not implemented** | Connections/community | Target navigation includes Installed/Available; no implementation evidence. |

## 3.15 Search, dashboard, navigation and UI

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Dashboard | **Implemented** | Foundation | Existing navigation and later prompts added reconciliation/completeness/service metrics. |
| Dashboard reconciliation counts | **Implemented** | B/UI | Project transcript says dashboard reconciliation counts were implemented. |
| Dashboard Service metrics | **Implemented** | C1 | Completed C1 prompt added compact Service summary counts. |
| Dashboard backup/recovery risk metrics | **Planned but not implemented** | D | Target Dashboard includes backup/recovery gaps and critical services at risk. |
| Dashboard stale evidence/discovery health | **Partially implemented/unknown** | A/B | Evidence and discovery models exist; exact dashboard widgets are not established. |
| Stable navigation domains | **Implemented** | UI architecture | Overview, Operations, Knowledge and System are in active navigation; future items are hidden until functional. |
| Changes under Overview | **Implemented** | UI refinement | Completed navigation prompt retained this placement. |
| Discovery under Operations | **Implemented** | UI refinement | Current navigation target and completed prompt. |
| Reconciliation under Operations | **Implemented** | UI refinement | Current navigation target and completed prompt. |
| Knowledge Gaps under Operations | **Implemented** | UI refinement | Completed prompt created dedicated nav item. |
| Services under Knowledge | **Implemented** | C1 | Completed C1 navigation. |
| Business Functions under Knowledge | **Implemented** | C1 | Completed C1 navigation. |
| Administration under System | **Implemented** | UI refinement | Completed prompt renamed/redirected System Settings nav to Administration `/admin`. |
| Alerts navigation | **Planned but not implemented** | Future Overview | Target-state Navigation includes Alerts but says only functional items should appear. |
| Impact Analysis navigation | **Planned but not implemented** | E | Target-state Navigation includes it; no functional route yet. |
| Backup & Recovery navigation | **Planned but not implemented** | D | Target-state Navigation includes it; no functional route yet. |
| Documentation navigation | **Planned but not implemented/unknown** | F | Target-state Navigation includes it; architecture has documentation boundaries, but usable route is not established. |
| Integrations navigation | **Partially implemented/unknown** | Connections | Architecture mentions integration boundaries; current active navigation state is not established. |
| Data Sources navigation | **Implemented at model level; route unknown** | A/Connections | DataSource exists; active source-centric view is uncertain. |
| Asset Type quick filters | **Implemented** | UI refinement | Completed prompt added top-ten type filters ordered by count and More dropdown. |
| Asset Type quick-filter counts | **Implemented** | UI refinement | Completed prompt required scoped API counts. |
| Asset/Knowledge Graph filter typography consistency | **Implemented** | UI refinement | Completed prompt matched Assets button font to Knowledge Graph controls. |
| Changes compact filter toolbar | **Implemented** | UI refinement | Completed prompt. |
| Knowledge Gaps compact filter toolbar | **Implemented** | UI refinement | Completed prompt matched Changes page. |
| Route-safe query filters | **Implemented** | UI hardening | Completed prompts explicitly fixed client-side blank/error state and preserved Back/Forward. |
| Login page uses main Atlas logo | **Implemented** | UI refinement | Completed prompt replaced text treatment with shared logo. |
| Transparent logo wrapper | **Implemented** | UI refinement | Completed prompt removed background box, border and shadow around logo. |
| Knowledge Completeness card padding alignment | **Implemented** | UI fix | Completed focused prompt fixed body/header alignment. |
| Knowledge Gap card hierarchy and compactness | **Implemented** | UI refinement | Completed prompt redesigned metadata, missing field, dates, next step and actions. |
| Left-aligned Knowledge Gap actions | **Implemented** | UI refinement | Explicitly required in completed prompt. |
| “Provide information” as primary Gap action | **Implemented/likely** | UI refinement | Completed prompt recommended making it the primary/obvious action. |
| Global keyboard shortcut search (`⌘K`) | **Unknown** | UI/search | Screenshot shows the affordance, but no functional implementation evidence. |
| Notifications bell and notification centre | **Unknown/planned** | UI/Alerts | Screenshot shows a bell/count, but no transcript evidence establishes notification behavior. |
| Light/dark appearance toggle | **Implemented/likely** | UI | Top bar screenshot shows theme icon; Profile supports appearance/accent. Exact mode implementation is not independently described. |

## 3.16 Product outputs and operational intelligence

| Product feature | Status | Release | Concrete evidence |
|---|---|---:|---|
| Missing documentation detection | **Implemented in generic completeness form** | Knowledge Completeness | Knowledge Gap rules can require fields, relationships and documentation links. |
| Missing ownership detection | **Implemented for Assets/Services where rules configured** | Knowledge Completeness/C1 | Service completeness includes owner/contact/support gaps. |
| Missing backups detection | **Partially implemented** | C1/D | A BACKED_UP_BY relationship/gap could be configured, but full backup coverage model is not built. |
| Single point of failure detection | **Planned but not implemented** | E | Alpha vision and impact analysis imply this. |
| Security concern recommendations | **Planned but not implemented** | Future operational intelligence | Alpha vision lists security concerns. |
| Version inconsistency detection | **Planned but not implemented** | Future operational intelligence | Alpha vision lists version inconsistencies. |
| Capacity concern detection | **Planned but not implemented** | Future operational intelligence | Alpha vision lists capacity concerns. |
| Configuration drift | **Partially implemented** | B/F | Observed vs accepted contradictions exist; intended-state drift via NetBox remains Release F. |
| Lifecycle history after removal/move | **Implemented for no-longer-observed/reobserved; broader lifecycle partial** | A/B | Discovery history preserves no-longer-observed and re-observed states. |
| Recommendations rather than raw reporting | **Partially implemented** | Knowledge Completeness | “Next step” guidance and gaps provide recommendations; broader AI/operational recommendations remain future. |
| Executive summaries | **Planned but not implemented** | F | Alpha vision output. |
| Disaster Recovery guides | **Planned but not implemented** | D/F | Alpha vision output. |
| Architecture documentation generation | **Planned but not implemented** | F | Alpha vision output. |
| APIs as output/context interface | **Implemented at application API level; external public contract maturity unknown** | Foundation | FastAPI APIs exist; roadmap says future plugin-safe contracts should avoid ORM leakage. |
| AI context API | **Planned but not implemented** | Future AI layer | Alpha vision says Atlas should expose structured context through open interfaces. |

---

# 4. Explicitly deferred or out-of-scope items

The following were not omissions; they were deliberately excluded from the current MVP/release:

1. **Full enterprise ownership model**
   - Person
   - Team
   - Team Membership
   - structured Service Role Assignments
   - ownership history
   - escalation schedules
   - on-call rosters

2. **Formal knowledge objects**
   - Decision
   - Assumption
   - Exception
   - Runbook
   - review/expiry workflow
   - rich collaborative authoring

3. **Full backup and recovery domain**
   - Backup Policies/Jobs/Copies/Repositories
   - Recovery Plans/Steps/Tests
   - structured protection status and recovery confidence

4. **Impact analysis**
   - Simulate failure
   - blast radius
   - bounded evidence-backed dependency paths
   - direct/downstream/uncertain impact
   - recovery readiness score

5. **Generated operational documents and intended state**
   - deterministic narrative documents
   - DR pack
   - NetBox connector
   - intended-versus-observed reconciliation

6. **Advanced authentication**
   - SSO
   - MFA
   - email recovery
   - break-glass command
   - active-session management

7. **Advanced worker orchestration**
   - recurring discovery schedules
   - mature asynchronous job management

---

# 5. Explicitly abandoned or superseded approaches

| Approach | Classification | Why |
|---|---|---|
| Neo4j/graph database as a prerequisite | **Abandoned** | PostgreSQL was explicitly retained; semantic entities, edges, provenance and temporal behavior define the knowledge graph. |
| Generic polymorphic relationship table for all C1 entities | **Abandoned for current architecture** | Typed ServiceAssetDependency, ServiceDependency and ServiceBusinessFunction tables were preferred for referential integrity. |
| Separate first-class Application and Service business models in C1 | **Abandoned/superseded** | The design chose first-class Service plus the existing Application Asset Type. |
| Automatically converting existing Application/Service Assets into Services | **Abandoned for C1** | C1 explicitly prohibited automatic migration and duplicate creation. |
| Replacing the Application Asset Type | **Abandoned** | It was explicitly retained for deployed software instances. |
| Keeping an ambiguous Service Asset Type as the main service concept | **Superseded** | First-class Service now owns the operational-capability concept; old Asset Type remains only for compatibility and may be renamed. |
| Full enterprise Release C in the first homelab implementation | **Abandoned for C1** | Scope was deliberately reduced to a useful homelab vertical slice. |
| Split-origin frontend/API as preferred production architecture | **Superseded** | Same-origin `/api` became the preferred generic deployment. |
| Cloudflare-specific application design | **Abandoned/prohibited** | Cloudflare is optional deployment infrastructure only. |
| Bottom-left Profile navigation as the account entry point | **Abandoned/removed** | Replaced by the top-right account dropdown. |
| Opaque AI-generated recovery score | **Abandoned/prohibited** | Readiness must be based on structured gaps and explainable evidence. |
| NetBox as Atlas’s mandatory system of record | **Abandoned/prohibited** | NetBox is an optional intended-state source. |
| Embedding one specific AI model into Atlas core | **Abandoned/not intended** | Atlas should remain AI-tool agnostic and expose structured context. |

---

# 6. Unknown items requiring repository verification

These features were mentioned or implied, but the transcript does not give enough evidence for a reliable status:

- Full global Search Atlas behavior and `⌘K` command palette.
- Notification bell/notification centre behavior.
- Complete duplicate detection and merge workflow in Reconciliation.
- Reclassify and Add Explanation reconciliation actions.
- Full live Proxmox discovery-to-reconciliation path versus simulation-only coverage.
- Docker discovery/plugin implementation status.
- Proxmox Backup Server plugin status.
- Active Integrations and Data Sources UI routes.
- Existing generated-document functionality and quality.
- Full provenance coverage on every relationship.
- Assignment/user workflow for Knowledge Gaps.
- Production readiness of scheduled/queued worker jobs.
- Current repository licence and formal 0.1 release status.
- Community LXC installer and Portainer deployment artefacts.

These should be checked directly against the repository before being marked complete in a public roadmap.

---

# 7. What remains to build

## Immediate next release: C2 — Service Graph and impact foundations

The homelab Service MVP is now present. The next useful vertical slice should improve operational value without jumping immediately into enterprise people/process modelling.

Build:

- clearer Service dependency map and focus modes;
- Asset→Service reverse traversal;
- “what Services depend on this Asset?”;
- business-function linkage paths;
- bounded traversal service with cycle detection and depth limits;
- evidence path returned with graph results;
- early impact preview without claiming full Release E readiness;
- Service/Application association workflow for existing Application Assets;
- optional assisted creation of Services from discovered Application Assets, always requiring confirmation.

## C3 — Structured ownership for MSP use

Build:

- Person;
- Team;
- Team Membership;
- Service Role Assignment;
- Business Owner;
- Technical Custodian;
- Support Group;
- primary/secondary responsibility;
- effective dates/history;
- ownership and escalation views;
- missing/unassigned responsibility reporting.

Migrate simple C1 owner/contact/support text fields safely into structured assignments.

## C4 — Formal operational knowledge objects

Build:

- KnowledgeObject;
- Decision;
- Assumption;
- Exception;
- Runbook;
- links to Services, Assets, Business Functions and Recovery Plans;
- review, expiry and reconfirmation;
- lightweight Markdown authoring;
- provenance and Changes integration.

## Release D — Backup and Recovery Model

Build:

- Backup Policy;
- Backup Job;
- Backup Copy;
- Backup Repository;
- Recovery Plan;
- Recovery Step;
- Recovery Test;
- last successful backup evidence;
- recovery prerequisites;
- ordered recovery editor;
- critical-Service coverage and gap reporting;
- PBS integration first;
- later Veeam and other backup platforms.

## Release E — Impact and Recovery Analysis

Build:

- “What happens if this disappears?”;
- Simulate failure;
- explainable blast-radius traversal;
- direct/downstream/uncertain impact;
- customer/site boundaries;
- evidence paths;
- affected Services, Business Functions and owners;
- backup coverage and recovery plan inclusion;
- structured recovery-readiness status.

## Release F — Knowledge Outputs and Intended State

Build:

- deterministic Asset, Service, Site, Recovery and Impact documents;
- Markdown/export templates;
- source and freshness references;
- risks, gaps and unresolved questions;
- operational handover pack;
- DR pack;
- NetBox connector;
- intended-state assertions;
- observed-versus-intended reconciliation.

## Production/community release work

Build or verify:

- Proxmox LXC community installer;
- Portainer/GitHub Compose deployment;
- clean `.env.example`;
- release upgrade/rollback tests;
- removal of obsolete MVP wording;
- licence selection and `LICENSE`;
- contribution guide;
- security policy;
- release notes/changelog;
- versioning and 0.1 tag;
- supported deployment matrix;
- backup/restore validation;
- health/monitoring guidance.

## Integration roadmap after Proxmox/PBS

Suggested priority:

1. Docker
2. UniFi
3. Nginx Proxy Manager
4. Authentik
5. Home Assistant
6. Veeam
7. Fortinet
8. Check Point
9. Meraki
10. VMware/Hyper-V
11. ITSM and documentation systems
12. NetBox as intended-state input

---

# 8. Proposed revised release plan

| Release | Scope | Current state |
|---|---|---|
| **0.1 Foundation** | Authentication, RBAC, tenancy, Assets, Networks, Relationships, custom fields, administration, single-origin deployment | **Implemented; release packaging still to verify** |
| **A Knowledge Foundation** | Evidence, assertions, provenance, history, truth classifications, meaningful Changes | **Implemented** |
| **B Discovery Reconciliation** | Staged discovery, reconciliation, no-longer-observed, re-observed, contradictions, operator decisions | **Implemented in workflow; live integration proof may need verification** |
| **B.5 Knowledge Completeness** | Requirement definitions, Knowledge Gaps, evaluator, defer/exception, Asset and Service completeness | **Implemented** |
| **C1 Homelab Service MVP** | Services, Service Types, Criticality, dependencies, Business Functions, simple ownership, RTO/RPO, service gaps and graph | **Implemented** |
| **C2 Service Graph and Impact Foundations** | Reverse traversal, focused dependency paths, evidence paths, bounded graph traversal | **Next recommended build** |
| **C3 MSP Ownership** | People, Teams, role assignments, escalation and ownership views | **Deferred/planned** |
| **C4 Operational Knowledge Objects** | Decisions, Assumptions, Exceptions and Runbooks | **Deferred/planned** |
| **D Backup and Recovery** | Backup/recovery domain and coverage workflows | **Planned** |
| **E Impact Analysis** | Explainable blast radius and recovery readiness | **Planned** |
| **F Knowledge Outputs and Intended State** | Narrative documents, DR packs and NetBox intended-state reconciliation | **Planned** |

---

# 9. Recommended next-step decision

Before starting another large Codex implementation, perform a short repository verification against the **Unknown** list, particularly:

1. whether live Proxmox discovery is flowing through Evidence → Assertions → Reconciliation;
2. whether Docker and PBS integrations already have meaningful code;
3. whether generated documents are functional or merely architectural scaffolding;
4. whether the community/0.1 deployment work has already landed outside this transcript;
5. whether C1 Service features all have migrations, tests and production navigation enabled.

Once verified, the highest-value next build is likely **C2 — Service Graph and Impact Foundations**, followed by **Release D — Backup and Recovery**, because those two steps create the homelab demonstration that most clearly differentiates Atlas:

> Select an Asset or Service, see what depends on it, why it matters, whether it is protected, and what is missing for recovery.
