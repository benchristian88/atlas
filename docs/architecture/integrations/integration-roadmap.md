# Integrations I0–I8 roadmap

**Active target programme**, I3 implementation evidence updated 12 October 2026.
The original alignment on 11 October 2026 used
`90e04a76982c314fff2191e84ca6bd1a8cabcb07`.
The [v1.3 design](Atlas_Integration_Architecture_and_Design_Specification_v1.3.md)
is the single active Integration specification; the
[alignment matrix](integration-alignment-matrix.md) determines current owners.
Accepted decisions/contracts do not establish end-to-end implementation.

H1–H5 core hardening is the existing foundation. Preserve installation/MFA/
backup/restore/release/update behavior and recorded outstanding package/platform
acceptance. I8 qualifies integration additions and carries those genuine gaps
forward, without rebuilding hardening or claiming whole-product certification.
Manual knowledge and explicit manual-only deployment remain supported.

| Phase | Target scope | Current status / acceptance boundary |
| --- | --- | --- |
| I0 | Repository audit, one v1.3 architecture, durable ADRs, staged AIP/Manifest/interface specs and sanitized examples/tests | Specification components implemented; runtime/vendor feature still partial foundations only. See completion/validation record. No production schema, API, permissions or UI changes. |
| I1 | Runtime and catalogue shell | Implemented shell with documented follow-ups. Authenticated isolated local health/control, pinned baseline, protected verified-package store, global installed state/RBAC, offline metadata and real UI, both installer/package definitions. External SDK extraction uses the explicitly authorized isolated staging adapter fallback; remote provenance fails closed. I1 originally deferred live Docker/systemd acceptance; I2 now records operator-confirmed Docker acceptance, while native/systemd remains pending. See [completion/validation](i1-completion-report.md). No live discovery, source credentials or scheduling/AIP callbacks. |
| I2 | Generic Integration, SecretProvider, mappings and bounded Test Connection | Implemented with documented external acceptance follow-ups. Canonical SDK 1.1.0, scoped config/DataSource, write-only encrypted credentials/portable rewrap, global versioned mappings/update gates, manifest forms and exact verified runtime probes. Live Docker image build/upgrade, offline bootstrap staging, UI configuration and fingerprint-pinned Proxmox 9.2.11 probes (including after runtime restart) are operator-confirmed. Proxmox 0.1.0 remains unqualified and Test Connection-only; native/systemd and remote provenance acceptance remain follow-ups. See [I2 evidence](i2-completion-report.md). |
| I3 | Worker orchestration and AIP ingestion | Implemented generic execution path with documented deployment follow-ups. Durable PostgreSQL runs/receipts/provenance, existing worker/Redis, fixed schedules, immediate authorized onboarding/Run Now, database overlap protection, run-scoped tokens, verified async runtime start/status/cancel, bounded recovery and canonical adapters into existing evidence/reconciliation/lifecycle. Production UI capability-gates probe-only Proxmox. Deterministic test-only execution acceptance and actual Docker/LXC build/deployment, migration, retained I2 probes, signing-state restart preservation and isolation/hardening are confirmed; native Debian/systemd LIVE acceptance remains outstanding. No production discovery Connector or I4 qualification. See [implementation](i3-implementation.md) and [validation](i3-completion-report.md). |
| I4 | Proxmox | Planned but not implemented through AIP. Preserve existing plugin/client/normalization regressions. Mandatory dated external review, exact least-privilege API-call/ACL matrix, dedicated token/Privilege Separation setup, capability/TLS/permission probe, stable infrastructure identity and coverage edge-case fixtures/live tests. |
| I5 | Docker/Compose | Planned but not implemented. SSH key only, documented Docker daemon/group root-equivalent access, stable Engine/project/service/ordinal workloads, container ID as observed provenance. Prove standalone rename/recreate/scale/one-off identity, Networks/Interfaces, host correlation and bounded source failures. |
| I6 | UniFi Network | Planned but not implemented. Local controller/console infrastructure only; prove documented local API-key provisioning has no unwanted cloud dependency or qualify dedicated local least-privilege read-only fallback. Gateway/switch/AP, site context, canonical Networks/Interfaces, reliable source-backed uplinks; no clients. |
| I7 | Onboarding and operations | Planned but not implemented. Resumable setup, grouped explicit Accept all new, duplicate/conflict review, manual-only path, fixed schedule UX, run health and source-permission documentation; preserve v1.2 page/mockup baseline and canonical UI primitives. |
| I8 | Integration release hardening/security/package acceptance | Planned but not implemented. Qualified offline three-bundle snapshot, protected provenance verification/install/update/rollback/uninstall, all dependent config gates, credential/non-disclosure/tenant boundaries, restore/recovery, both package methods, failure/performance/accessibility/browser acceptance and dependency/licence/SBOM review. |

## Exact I1 implementation boundary

1. Before implementation, move the two new schemas verbatim into
   `atlas-connector-sdk` and establish released SDK consumption/ownership. Do not
   turn documentation staging into a second production SDK or relicense legacy
   AGPL plugin implementation by assumption. No remote repo creation was done in I0.
2. Add runtime source in main Atlas repo, isolated service/client health,
   capabilities and protected installed-reference verification with independent
   installation service credential. Private Compose and loopback native/systemd
   implementations use the same contract; no Docker requirement for native.
3. Extend current installers/package manifests for normal default runtime and
   explicit manual-only opt-out, pinned approved environment and protected store.
   Runtime cannot mutate the store or access canonical PostgreSQL directly.
4. Implement generic catalogue metadata/shell verification and instance-global
   installed-package state with Available/Installed/Update available/Runtime
   update required/Update requires configuration/Incompatible states. Choose
   attestation verification implementation and prove offline trust/path bounds;
   explicit global-admin actions and one-active-version rules remain mandatory.
5. Preserve the supplied mockup page structure, use sibling Atlas primitives,
   and extend current Integrations route. UI implementation is I1+, not I0.

I1 shell may need additive persistence/RBAC for runtime/package state; it must
follow existing migration/permission conventions. It does not add Integration
credential storage, job scheduling, AIP callbacks or vendor code. Until I4–I6
qualification, the I0 example manifests/empty dependency locks are non-installable
and cannot be advertised as working offline bundles. The final integration
release must embed all three qualified bundles; shell acceptance is not release
acceptance or permission to substitute unverified packages.

## I4 mandatory external-reference gate

**Current review date: pending I4.** I0 records this requirement on 11 October
2026; no current upstream permission/version/community findings are claimed.
Before I4 implementation/acceptance, date the review and repeat at qualification:

1. [Official Proxmox VE Administration/API documentation](https://pve.proxmox.com/pve-docs/pve-admin-guide.pdf)
   and exact supported live API behavior are authoritative.
2. [Home Assistant Proxmox VE setup](https://www.home-assistant.io/integrations/proxmoxve/)
   is secondary operator wording/least-privilege evidence.
3. Secondary operational evidence:
   [permissions](https://github.com/dougiteixeira/proxmoxve/blob/main/docs/permissions.md),
   [releases](https://github.com/dougiteixeira/proxmoxve/releases),
   [issues](https://github.com/dougiteixeira/proxmoxve/issues),
   [cluster discussion 587](https://github.com/dougiteixeira/proxmoxve/discussions/587).

Record review date, URL, relevant source/release versions, adopted finding,
Atlas fixture/regression or documented out-of-scope rationale. Official Proxmox
wins conflicts; document discrepancy. Do not copy referenced third-party code.
Candidate `VM.Audit`/`Sys.Audit`/`Datastore.Audit` is not final policy;
`VM.GuestAgent.Audit` is requested only if actual consumed calls need it.
Prove final role/ACL/path matrix from shipped calls with a dedicated `atlas@pve`
identity/token (for example `atlas@pve!discovery`), Privilege Separation on and
sufficient backing-user permissions, without root/admin/password fallback.

## Seeded I4 edge-case register

All items are **pending I4 evidence and regressions**, not current implemented
capabilities. Add materially relevant current release/issue lessons at review.

| Case | Required qualification consequence |
| --- | --- |
| Configured-node outage / endpoint resilience | Cluster fallback where supported; no whole-cluster false absence from one unavailable node. |
| Cluster membership changes | Join/leave/transient failure preserves stable source links and partial coverage. |
| Shared vs local storage | Shared/Ceph deduplication, distinct node-local storage and deterministic collision fixtures. |
| Physical disk identity | WWN/serial/by-id where available; no mutable devpath/display-name identity. |
| Missing optional disk identifiers | Explicit deterministic fallback and collision tests; unsupported claims omitted. |
| Storage/API limitations | Honest omitted/partial scope where enumeration cannot be proven. |
| Permission-limited visibility | Exact missing capability/path; affected aggregate scope partial, never absence. |
| Optional guest agent | Base guest discovery works without agent/extra privilege; optional facts have honest coverage. |
| Source-version compatibility | Supported, newer/untested warning allowed, known incompatible blocked with update guidance. |
| TLS/self-signed/fingerprint changes | Validate trust before credentials; changed pin fails safely; insecure exception visibly warned. |
| Slow/unavailable nodes | Bounded timeout/concurrency/retry; no falsely completed scope. |
| Pagination/large inventories | Bounded pages/results/body/run sizes with partial status on truncation. |

## Remaining implementation research

I1: external SDK publishing/rights, reviewed GitHub/Sigstore verifier/trust roots,
and native/systemd live lifecycle acceptance remain documented follow-ups.
Protected store, exact bootstrap verification, pinned baseline and both deployment
definitions are implemented; Docker operator evidence is recorded in I2 and I3.
I3: native Debian/systemd LIVE acceptance remains outstanding; actual Docker/LXC
deployment, migration and signing-state restart preservation are operator-confirmed.
I4: dated source
review, Collection/API coverage and final call/ACL matrix. I5: Collection/SSH
implementation and workload ordinal/standalone identity proof. I6: supported
local API capabilities and API-key/local fallback authentication. I8: exact
licence/SBOM inventory and empirical resource/performance/package acceptance.
These are evidence questions, not reopened product-policy decisions.
