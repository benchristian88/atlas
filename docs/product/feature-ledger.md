# Product feature reference

This reference describes the checked-in beta platform, inspected on 4 October
2026 from base commit `e63b552c1149c883cc9b103d9aa6c85eb129a717`, with the public
documentation and licence changes at that baseline. Integration specification
status was updated on 11 October 2026 against
`90e04a76982c314fff2191e84ca6bd1a8cabcb07`; the runtime/catalogue shell was added
after merged baseline `77eeff71e9a803f0f665ffa150b24537e29b83a6`.
I2 implementation was updated on 12 October 2026 after merged I1 baseline
`7e2a8c9ec1e04b27e1f32153347380f05d4d9a59`. Current implementation and validation
boundaries are recorded in the [I2 report](../architecture/integrations/i2-completion-report.md).
I3 generic orchestration/ingestion is implemented on the I2 baseline; current
validation is recorded in the [I3 report](../architecture/integrations/i3-completion-report.md);
the [I1 record](../architecture/integrations/i1-completion-report.md) remains historical.
Code, migrations,
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
| Evidence, assertions and Changes | Implemented | Knowledge models/services/routes and history/Changes UI. The evidence/reconciliation path separates observations from accepted knowledge; the [Integration alignment audit](../architecture/integrations/integration-alignment-matrix.md) documents different legacy direct-sync behavior that new ingestion must bypass. |
| Discovery simulation and reconciliation | Implemented | Simulation/run routes, normalized ingestion and independent reconciliation decisions. Generic [entity review](../architecture/reconciliation-entity-review.md) groups Asset facts, relationships and owned Interfaces with backend eligibility, prerequisite jumps, scoped entity/record totals, bounded cursor pages and independently paged sections. Accept asset preserves child decisions; explicit Accept all uses the existing audit/decision path and reports blocked/failed work. Candidate headings use observed or accepted names while retaining source identity. Discovery summaries show friendly source/structured scope with separate connector/trigger and status/completeness. Archived-run reconciliation suppression remains unimplemented because coalesced assertions lack contributing-run provenance. Live plugin operation is separate. |
| Knowledge completeness | Implemented | Structured requirements, profiles, idempotent evaluation, summaries and gap lifecycle for Assets and Services. Broader entity coverage is deferred. |
| Asset icon caching | Implemented | Bounded HTTPS retrieval and authorized local serving with existing fallback chain. |
| Encrypted application backup/restore | Implemented | `services/backups.py`, backup/setup routes, Backup & Restore UI and CLI. Portable `.atlasbackup`, target-local secrets and MFA/Integration credential rewrap; 2 GiB bound and one API runtime. |
| Docker Compose installation | Implemented | `infra/install/compose.py`, protected configuration, single gateway, private internal services and persistent volumes. |
| Native/systemd installation | Implemented | `infra/install/native.py`, managed nginx ingress, unprivileged services and read-only preflight on prepared Debian/Ubuntu hosts. |
| Packaged release distribution | Implemented | `infra/release/`, version/channel policy, package manifest, hashes and isolated publication workflow. Publication is deliberate; no registry or signing/attestation claim. |
| Configuration-preserving upgrades | Implemented | `infra/install/upgrade.py` for both package methods, backup confirmation and health checks. Real native upgrade is operator-confirmed; an existing Docker deployment was successfully upgraded during live I2 acceptance, including real image builds and migration to `20261012_0028`. No automatic rollback or self-update. |
| Informational update checks | Implemented | `services/updates.py`, global System Settings APIs and Updates card. Fixed public GitHub source, bounded cache/network reads and offline failure handling. |
| Development CI | Implemented | `.github/workflows/ci.yml`: Backend / PostgreSQL, Frontend, Release & Deployment Integrity. Release publication stays separate. |
| Public documentation and licence | Implemented | Root policies, operator guides, About project links and AGPL-3.0-only package metadata. |

## Partial foundations and upcoming product work

| Capability | Status | Boundary |
| --- | --- | --- |
| Live first-party integrations/plugins | Partially implemented | `plugins/sdk`, tested `plugins/proxmox` adapter and Data Source/Integration persistence exist. Complete configure/test/Run Now/results/reconcile journey remains upcoming. Worker is a placeholder, not mature job orchestration. |
| Canonical Integration contracts | Implemented | Separate Apache-2.0 SDK 1.1.0 consumed by exact hash in Atlas and official Connectors. Original AIP/Manifest v1 bytes unchanged; additive Manifest 1.1 probe-only support. Documentation schema files are references; legacy AGPL plugin code unchanged. |
| Runtime and catalogue shell | Implemented | Authenticated isolated runtime, protected exact-package store, global installed-state/RBAC and Configured/Catalogue/Runtime UI. Pinned Proxmox Test Connection-only bootstrap package; Docker/UniFi are metadata only. Docker image builds/upgrade, trusted bootstrap staging and UI package installation are operator-confirmed. Native runtime/platform acceptance and remote catalogue/package consumption remain follow-ups; B1.2 separately verifies supplied provenance. |
| B1.1 official catalogue structural validator | Implemented | Offline strict byte parser, exact six-field v1 envelope, canonical SDK Manifests, official distribution declarations, raw/canonical 4 MiB bounds, 200 entries and canonical standalone 256 KiB entry bound. Frozen published sequence-1 compatibility fixture. Internal structural component only: no retrieval, cryptographic trust, persistence, installation or UI integration. Separate B1.2 provenance methods do not promote structural results. See [contract boundary](../architecture/integrations/official-catalogue-v1.md). |
| B1.2 official artifact provenance | Implemented | Internal offline cryptographic component: pinned GitHub CLI 2.102.1, reviewed Public Good roots, distinct catalogue/package signer profiles, numeric certificate identities and original-byte digest binding. Genuine sequence-1 and package verification demonstrated; deterministic real-verifier tests required. API Docker amd64/arm64 packaging/offline acceptance tested; native preparation integrated, full systemd acceptance outstanding. No remote retrieval, persistence, installation or UI; mutable existing releases require publication hardening before B1.3/B3. See [trust and deployment contract](../deployment/attestation-verification.md). |
| B1.3 official catalogue consumer | Partially implemented | Bounded fixed-source public retrieval, genuine B1.2 pipeline, two PostgreSQL trust tables, leases/coalescing, sequence/history/withdrawal checks and global status/manual-refresh APIs are implemented foundations. Live exact-byte verification succeeds; trusted promotion fails closed because `catalogue-v1` is mutable and no approved separate advancing current channel exists. No accepted live remote revision, package installation, scheduler or frontend changes. See [consumer/operator contract](../deployment/official-catalogue.md) and [publication prerequisite](../architecture/integrations/b1-3-publication-plan.md). |
| Generic configuration and Test Connection | Implemented | Scoped Integration/DataSource, manifest-driven create/detail, write-only AES-GCM credentials using existing data key/portable rewrap, global versioned taxonomy mappings, safe update ownership gates and bounded verified private-runtime probes and generic capability readiness rendering. Live fingerprint-pinned Proxmox 9.2.11 authentication, saved encrypted credentials and probes after runtime restart are operator-confirmed. Source versions remain explicitly unqualified/untested; no discovery is claimed. See [I2 evidence](../architecture/integrations/i2-completion-report.md). |
| Generic discovery orchestration and ingestion | Implemented | I3 durable PostgreSQL runs/receipts/provenance, worker/Redis dispatch, fixed schedules, separate run credentials, verified bounded runtime jobs, canonical AIP into existing evidence/reconciliation/absence services, cancellation/recovery and existing UI extensions. Deterministic test-only executable acceptance; no production discovery Connector. Actual Docker/LXC build/deployment, migration to `20261012_0029`, retained I2 probes, signing-state restart preservation and isolation/hardening are operator-confirmed. Native Debian/systemd I3 LIVE acceptance remains outstanding. See [I3 evidence](../architecture/integrations/i3-completion-report.md). |
| Discovery diagnostics and next-run debug | Implemented | Runtime-owned bounded NDJSON, permanent normal run summary/context, global administrator-only one-shot debug intent, 48-hour expiry/physical purge and explicit deletion. Generic run UI/API and isolated failure/tenancy/real Runner fixtures; no raw source logging, SDK/AIP or source/completeness changes. Portable backups exclude debug data. See [contract](../architecture/integrations/discovery-diagnostics.md) and [validation](../architecture/integrations/i4c-diagnostics-report.md). |
| Production Connector inventory discovery | Partially implemented | Separate Proxmox discovery candidates implement secured collection discovery, source-local identities, bounded topology/facts and conservative ACL/coverage proof, with actual Ansible/AIP/I3 fixture acceptance. Official production Proxmox 0.1.0 remains discover=false and unqualified; normal activation rejects the candidate. Live 9.2.11 runs of 0.2.0-i4b.1 and 0.2.0-i4b.2 were PARTIAL (140 and 179 observations). The .2 fix retains the existing lxc_container recommendation; 0.2.0-i4b.3 adds bounded diagnostics without relaxing validation and remains unqualified. COMPLETE live coverage and native/systemd live acceptance remain outstanding. See [qualification fixes](../architecture/integrations/i4c-live-qualification-fixes.md) and [historical candidate evidence](../architecture/integrations/i4b-completion-report.md). |
| I4A runtime dependency groundwork | Implemented | Reviewed community.proxmox 2.0.0 archive/digest lock, pinned HTTPS Python dependencies, shared offline Docker/native installation, actual installed-content collection health and exact catalogue dependency compatibility. SBOM/notices and source-derived Connector capability/ACL docs updated. Inventory candidate work is separate; Proxmox 9.2.11 remains unqualified. See [baseline review](../architecture/integrations/i4a-runtime-baseline.md). |
| Local Connector qualification preparation | Implemented | Explicit installation-authority CLI, separate opt-in test store, exact expiring ID/version/bundle/manifest/commit authorization, existing package validation and independent runtime recheck. Candidate activation is local to the isolated test instance; normal catalogue/production qualification gates are unchanged. Proxmox 0.2.0-i4b.1/.2 and diagnostic successor 0.2.0-i4b.3, and source 9.2.11, remain unqualified; full live acceptance and I4C-B are outstanding. See [I4C-A preparation](../architecture/integrations/i4c-a-preparation.md). |
| Generated operational documents | Partially implemented | `services/markdown_docs.py` generates Markdown and Document records store it. Dedicated document browsing/review is not yet an end-to-end feature. |
| Guided onboarding | Planned but not implemented | Secure first-run administrator creation exists; guided initial knowledge setup is separate upcoming work. |
| Final screenshots and documentation freeze | Planned but not implemented | Feature descriptions and screenshots will be refreshed after integration/onboarding work. No stale product screenshots are advertised. |
| Final security/release qualification | Planned but not implemented | Core hardening closure supports continued beta development; final dependency review, cross-deployment acceptance and whole-product security/release qualification follow integrations and onboarding. Known dependency findings are not claimed resolved. |

## Deliberately deferred

Structured People/Teams, formal Knowledge Objects, evidence-backed recovery
readiness, enterprise impact scoring, intended-state/change simulation, ITSM,
production-scale orchestration and additional discovery Connectors beyond the
three initial Proxmox/Docker/UniFi references are deferred. Those three follow
the accepted Integration programme; they are not already live configured features.
Service RTO/RPO fields describe objectives, not proof of recoverability. Atlas
application backups do not implement an infrastructure protection/recovery model.
No automatic conversion of legacy Service/Application Assets is planned as an
implicit migration.

The [project status](status.md) is the concise active roadmap. Detailed dated
audits and execution records are preserved under `docs/history/`; their original
milestone terminology and results are historical evidence.
