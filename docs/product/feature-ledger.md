# Product feature reference

This reference describes the checked-in beta platform, inspected on 4 October
2026 from base commit `e63b552c1149c883cc9b103d9aa6c85eb129a717`, with the public
documentation and licence changes in the current working tree. Code, migrations,
reachable routes and regression tests determine implementation status. A status
here does not claim that validation was rerun; current execution results are
recorded separately.

## Implemented capabilities

| Capability | Status | Repository evidence and boundaries |
| --- | --- | --- |
| Scoped inventory and managed taxonomy | Implemented | `apps/api/app/models.py`, Asset/Interface/Network and reference-data routes; corresponding web pages. Customer/site scope enforced by API. |
| Local authentication and administration | Implemented | Auth, Users, Roles, context and System Settings routes; cookie sessions, permission assignments, profile and audit UI. |
| Secure first-run setup | Implemented | `routes/setup.py`, singleton installation state, local setup-code tools and `/setup`. No environment-created administrator. |
| Optional TOTP MFA | Implemented | `services/mfa.py`, MFA routes, encrypted seeds, recovery verifiers, profile enrollment and local reset. No SSO or mandatory enrollment policy. |
| Services and Business Functions | Implemented | First-class models/routes and catalogue/detail pages. Distinct from Application or legacy Service Assets. |
| Temporal dependencies | Implemented | Service→Asset, Service→Service and Service→Business Function records retain ended history. |
| Dependency rules | Implemented | Dependency groups and membership, required/optional, `all`/`any`, unavailable/degraded/unknown effects. No quorum or weighted rules. |
| Operational graph | Implemented | `services/operational_graph.py`, generic/landscape routes and focused compatibility adapters. Bounded, authorized projection over PostgreSQL. |
| Dependency impact analysis | Implemented | `services/dependency_analysis.py`, `/api/dependency-analysis` and graph Analysis UI. Hypothetical unavailable inputs, path explanations and conservative unknown results. No live availability inference, structural Asset failure propagation or Business Function impact. |
| Dashboard and graph exploration | Implemented | Dashboard, Knowledge Graph Overview/Focus/Analysis, inspector, workspace viewpoints and responsive presentation. |
| Infrastructure Topology and Showcase | Implemented | Topology routes/UI over hosting, Network membership and recorded connectivity; presentation exports do not alter accepted knowledge. |
| History-preserving entity lifecycle | Implemented | `services/entity_lifecycle.py`, guarded Service/Function deletion and archive/restore. Tombstones retain history. |
| Evidence, assertions and Changes | Implemented | Knowledge models/services/routes and history/Changes UI. Observations never silently overwrite accepted knowledge. |
| Discovery simulation and reconciliation | Implemented | Simulation/run routes, normalized ingestion and reviewable reconciliation decisions. Live plugin operation is separate. |
| Knowledge completeness | Implemented | Structured requirements, profiles, idempotent evaluation, summaries and gap lifecycle for Assets and Services. Broader entity coverage is deferred. |
| Asset icon caching | Implemented | Bounded HTTPS retrieval and authorized local serving with existing fallback chain. |
| Encrypted application backup/restore | Implemented | `services/backups.py`, backup/setup routes, Backup & Restore UI and CLI. Portable `.atlasbackup`, target-local secrets and MFA rewrap; 2 GiB bound and one API runtime. |
| Docker Compose installation | Implemented | `infra/install/compose.py`, protected configuration, single gateway, private internal services and persistent volumes. |
| Native/systemd installation | Implemented | `infra/install/native.py`, managed nginx ingress, unprivileged services and read-only preflight on prepared Debian/Ubuntu hosts. |
| Packaged release distribution | Implemented | `infra/release/`, version/channel policy, package manifest, hashes and isolated publication workflow. Publication is deliberate; no registry or signing/attestation claim. |
| Configuration-preserving upgrades | Implemented | `infra/install/upgrade.py` for both package methods, backup confirmation and health checks. No automatic rollback or self-update. |
| Informational update checks | Implemented | `services/updates.py`, global System Settings APIs and Updates card. Fixed public GitHub source, bounded cache/network reads and offline failure handling. |
| Development CI | Implemented | `.github/workflows/ci.yml`: Backend / PostgreSQL, Frontend, Release & Deployment Integrity. Release publication stays separate. |
| Public documentation and licence | Implemented | Root policies, operator guides, About project links and AGPL-3.0-only package metadata. |

## Partial foundations and upcoming product work

| Capability | Status | Boundary |
| --- | --- | --- |
| Live first-party integrations/plugins | Partially implemented | `plugins/sdk`, tested `plugins/proxmox` adapter and Data Source/Integration persistence exist. Complete configure/test/Run Now/results/reconcile journey remains upcoming. Worker is a placeholder, not mature job orchestration. |
| Generated operational documents | Partially implemented | `services/markdown_docs.py` generates Markdown and Document records store it. Dedicated document browsing/review is not yet an end-to-end feature. |
| Guided onboarding | Planned but not implemented | Secure first-run administrator creation exists; guided initial knowledge setup is separate upcoming work. |
| Final screenshots and documentation freeze | Planned but not implemented | Feature descriptions and screenshots will be refreshed after integration/onboarding work. No stale product screenshots are advertised. |
| Final security/release qualification | Planned but not implemented | Existing tests and supplied acceptance support the beta; they do not replace final whole-product and dependency review. |

## Deliberately deferred

Structured People/Teams, formal Knowledge Objects, evidence-backed recovery
readiness, enterprise impact scoring, intended-state/change simulation, ITSM,
production-scale orchestration and multiple discovery plugins are deferred.
Service RTO/RPO fields describe objectives, not proof of recoverability. Atlas
application backups do not implement an infrastructure protection/recovery model.
No automatic conversion of legacy Service/Application Assets is planned as an
implicit migration.

The [project status](status.md) is the concise active roadmap. Detailed dated
audits and execution records are preserved under `docs/history/`; their original
milestone terminology and results are historical evidence.
