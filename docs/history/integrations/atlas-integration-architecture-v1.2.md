---
title: "Atlas Integration Architecture & Design Specification"
subtitle: "Ansible-based discovery runtime, Atlas-owned credential lifecycle, canonical observation protocol, and community collection model"
author: "Atlas Impact"
date: "28 September 2026"
version: "1.2"
status: "Community Preview"
---

**Historical / superseded.** Replaced by the
[active v1.3 design](../../architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md).
Original decisions below are preserved for provenance and are not current policy.
Five supplied UI mockups remain the implementation baseline; link destinations
have been repaired. Other exported diagrams were not supplied and are identified
by their original names without claiming an available artifact.

# Executive summary

Atlas already contains most of the difficult knowledge-management foundation required for an integration platform: scoped Customers and Sites, Assets, Networks and Interfaces, managed relationship types, Services and Business Functions, discovery runs, data sources, evidence, assertions, reconciliation, entity-source links, a shared operational graph, dependency analysis, and a vendor-neutral plugin SDK. The present gap is not another graph model. The gap is a reliable and scalable way to connect many external systems without making the Atlas core responsible for every vendor API.

This specification defines a homelab-first integration architecture that can grow naturally into small-business and MSP use without making Atlas an enterprise integration suite.

The central design decision is:

> **Atlas owns integration semantics, credentials, Atlas Integration Protocol (AIP), provenance, reconciliation, accepted knowledge, topology and the user experience. Ansible is the first reference execution runtime. An isolated Atlas Ansible Runtime uses Ansible Runner and pinned Execution Environments to consume maintained Ansible Collections wherever practical, then normalises their results into AIP.**

Ansible is deliberately separated from Atlas domain code. Atlas core does not import `ansible-core`, does not depend on Ansible internal APIs, and remains usable when the runtime is unavailable. The runtime is a separate process/container boundary. Its Execution Environment contains pinned Ansible components, collections and Python dependencies. AIP remains runtime-neutral so a future runtime or direct community collector can produce the same Atlas observations without changing the knowledge plane.

Source credentials are managed through an Atlas `SecretProvider`. The default homelab implementation stores encrypted secret material in Atlas using an established authenticated-encryption library and a master key held outside the database. Secret values are write-only from the UI and are materialised to the Ansible job only for the lifetime of that job. Ansible is not the system of record for credentials.

The first three reference connectors remain:

1. **Proxmox VE** — cluster, node, VM, LXC, storage and network/bridge discovery.
2. **Docker + Docker Compose** — Docker engines, Compose projects, containers, networks, volumes, ports and runtime relationships.
3. **UniFi Network** — controller/site context, gateways, switches, access points, Networks/VLANs, management interfaces and selected client observations.

The release objective is not to build every possible connector. It is to establish one runtime-neutral Connector contract, one canonical AIP ingestion model and one reliable execution boundary, then prove them with materially different sources. Atlas should prefer a maintained Ansible Collection for source API interaction, own only the source-to-AIP semantics and thin orchestration required for Atlas, and maintain a direct vendor client only where the collection ecosystem cannot provide the required read-only discovery.

Target integration architecture — original exported diagram `assets/architecture-context.png` was not supplied.

## Recommended release outcome

For the first public Atlas community release, an operator should be able to:

- install Atlas with the optional Atlas Ansible Runtime service enabled;
- complete guided Personal / Homelab onboarding;
- select Proxmox, Docker/Compose and optionally UniFi from the Atlas catalogue;
- enter source credentials through Atlas and have them stored by the configured Atlas `SecretProvider`;
- test each connection without exposing stored secret values;
- run discovery immediately through the isolated Ansible runtime;
- see discovered objects, relationships and coverage;
- accept or reconcile discovered knowledge into Atlas;
- schedule repeat discovery from Atlas;
- inspect run history and failures without opening an Ansible UI; and
- open the resulting topology and knowledge views.

The target first-value experience remains **fresh install to useful discovered topology in less than 15 minutes for a typical homelab**.

# 1. Purpose and scope

## 1.1 Purpose

This document is the build specification for the Atlas integration subsystem. It is intended to be sufficiently explicit that an AI development agent or engineering team can implement the subsystem in phases without re-deciding the main architecture.

It covers:

- current repository position and reusable code;
- architecture decisions and process/licensing boundaries;
- runtime-neutral `IntegrationRuntime` contracts with `AnsibleRuntime` as the first implementation;
- Ansible Runner and pinned Execution Environment design;
- Atlas-owned credential lifecycle through a `SecretProvider` abstraction;
- integration catalogue, Connector semantics and Ansible implementation packaging;
- generic Atlas integration data model;
- Atlas Integration Protocol v1;
- provenance and reconciliation behaviour;
- UI and guided onboarding;
- reference Connector designs for Proxmox, Docker/Compose and UniFi;
- security, supply-chain and secrets handling;
- operational status, scheduling, failure handling and lifecycle;
- Connector and collection compatibility/version policy;
- licensing and redistribution boundaries; and
- a phased development roadmap with Codex-ready prompts.

## 1.2 Product intent

Atlas is not intended to become a workflow automation or configuration-management product. Ansible provides a mature infrastructure automation ecosystem; Atlas uses it as an execution and source-access substrate while remaining an operational knowledge product. Atlas's durable responsibility is to define what external observations mean and how they become evidence, accepted knowledge and graph relationships.

The integration subsystem exists to make Atlas knowledge **living** rather than manually maintained. It should answer:

- What exists now?
- Where does it run?
- What is connected to what?
- What changed since the previous observation?
- Which observed facts disagree with accepted Atlas knowledge?
- Which entities disappeared from a complete source snapshot?
- What technical context can Atlas use to explain topology and potential consequences?

## 1.3 Non-goals for the initial release

The initial integration release does not need:

- arbitrary Ansible Collections or playbooks supplied by untrusted catalogue publishers;
- a public Connector marketplace;
- a general-purpose Ansible/AWX user interface inside Atlas;
- write/change automation against discovered infrastructure;
- centralized MSP remote workers;
- cross-customer discovery jobs;
- live time-series metrics ingestion;
- network packet capture;
- automatic creation of Business Functions;
- automatic conversion of discovered applications into first-class Services;
- automatic acceptance of every discovered change;
- an enterprise CMDB connector suite;
- replacement of Grafana, Uptime Kuma, Prometheus, UniFi monitoring or Proxmox monitoring; or
- a second persistent graph database.

# 2. Repository-grounded current position

The design deliberately extends the current repository rather than creating a parallel product.

## 2.1 Existing components to retain

| Existing capability | Repository location | Integration design use |
|---|---|---|
| `Integration` persistence model | `apps/api/app/models.py` | Evolve from Proxmox-shaped connection data into generic Integration instances. |
| `DataSource` | `apps/api/app/models.py` | Preserve as provenance identity for an Integration instance. |
| `DiscoveryRun` | `apps/api/app/models.py` | Extend with runtime job, trigger, Connector, Execution Environment and collection-lock metadata. |
| `EvidenceRecord` / observed entities | knowledge models/services | Preserve immutable source evidence and complete-snapshot coverage. |
| `EntitySourceLink` | `models.py`, `entity_resolution.py` | Preserve source identity to canonical Atlas entity mapping. |
| Assertions and reconciliation | `knowledge_assertions.py`, `reconciliation.py` | Continue separating observed source facts from accepted knowledge. |
| Complete-snapshot absence handling | `discovery_observations.py` | Reuse for missing/no-longer-observed handling. |
| Vendor-neutral plugin SDK | `plugins/sdk` | Evolve into the canonical AIP/Connector schema helper; no Ansible dependency in domain code. |
| Proxmox client/discovery/normalisation | `plugins/proxmox` | Reuse its tests and semantic mapping while migrating source access toward `community.proxmox`; do not maintain two production clients. |
| Discovery sync | `discovery_sync.py` | Reuse selected persistence helpers, but route runtime output through AIP evidence/reconciliation semantics. |
| Integration UI scaffold | `apps/web/app/integrations/page.js` | Replace mock data with real API and retain the existing Atlas design language. |
| Discovery Run UI | `apps/web/app/discovery-runs/page.js` | Retain and extend with runtime/Connector/job/Execution Environment metadata. |
| Worker boundary | `apps/worker` | Retain for Atlas-owned schedule dispatch, retries and background orchestration; it does not execute vendor API clients itself. |
| RBAC and customer/site scope | API authorization layer | Remains authoritative for all integration configuration, runs and ingestion. |

## 2.2 Current gaps this design resolves

The repository currently has a useful Proxmox adapter foundation but no complete configured-run journey. The current `Integration` model contains fields such as `base_url`, `username_or_token_id`, `secret_reference` and `verify_tls`, which are specific to the first Proxmox design. The Integrations page still uses mock records, and the Atlas worker does not dispatch isolated discovery jobs.

The new design resolves this by:

- making the Atlas `Integration` record generic;
- introducing an Atlas-owned `SecretProvider` abstraction and write-only credential lifecycle;
- introducing an explicit `IntegrationRuntime` abstraction;
- implementing `AnsibleRuntime` as an isolated service boundary using Ansible Runner;
- using pinned Execution Environments and Ansible Collections for source API interaction where practical;
- introducing a runtime-neutral Connector manifest that generates connection forms and defines semantics;
- keeping Atlas responsible for scheduling, run lifecycle, retries and user-visible status;
- defining a stable AIP observation payload; and
- preserving Atlas-owned evidence, assertions, entity resolution and reconciliation.

## 2.3 Roadmap change required

The checked-in roadmap deliberately deferred multiple plugins and broader worker automation. This specification intentionally reprioritizes that decision because the current product strategy is to release Atlas publicly and use homelab adoption as the integration/community wedge.

The active roadmap and feature ledger should be updated before implementation. The previous manual-first architecture remains valid for knowledge acceptance; what changes is the execution substrate. Community Preview should implement Ansible Runner first, but AIP and Connector semantics must remain runtime-neutral so Ansible never becomes part of Atlas's domain model.

# 3. Architecture decisions

## 3.1 Decision A — Ansible is the first external execution runtime

Atlas supports an external `IntegrationRuntime` boundary. The first implementation is `AnsibleRuntime`, backed by Ansible Runner and a pinned Execution Environment.

For the homelab release the preferred deployment is an optional, separate `atlas-ansible-runtime` service/container that can be started with the Atlas stack. It is operationally separate from the Atlas API and can fail without taking Atlas down. A remote runtime mode can be added later without changing Connector semantics.

The normal user does not need AWX, Ansible Automation Platform or an Ansible UI. Atlas remains the control plane and user experience.

## 3.2 Decision B — Atlas owns the durable integration contract

Ansible is an execution substrate, not the schema owner.

The durable contract is **Atlas Integration Protocol v1 (AIP v1)**. Any execution mechanism that can produce valid AIP batches can support Atlas in future.

```text
Atlas Integration Runtime interface
    ├── AnsibleRuntime          (Community Preview / v1 implementation)
    ├── RemoteCollectorRuntime  (possible MSP implementation)
    └── DirectAIPCollector      (community/custom integration path)
```

No Atlas domain service may import `ansible-core`, depend on Ansible internal Python APIs, or model Ansible inventory/playbook concepts as Atlas domain concepts.

## 3.3 Decision C — Atlas owns secret lifecycle through `SecretProvider`

Source-system credentials such as Proxmox API tokens, UniFi API keys, SSH private keys and TLS client keys are persisted through an Atlas `SecretProvider`, not in Ansible.

The default Homelab provider should:

- encrypt secret material at rest with an established authenticated-encryption library;
- keep the master encryption key outside the Atlas database, supplied through a deployment secret/file/environment mechanism;
- make secret fields write-only after save;
- never return plaintext credentials through Atlas APIs;
- never log secret values or complete submitted credential forms;
- support replace/rotate/delete without changing the Integration identity; and
- materialise only the secrets required for one job, then destroy the job material after completion.

The abstraction should permit a future external provider such as OpenBao without changing Integration records.

Ansible Vault is **not** the default Atlas credential store. It can protect Ansible variables/files at rest, but it does not remove the need for Atlas to manage the decrypting credential and secret lifecycle.

## 3.4 Decision D — Atlas remains authoritative for tenancy and knowledge acceptance

Connector implementations do not choose their Customer or Site.

A job payload may contain `integration_id` and `run_id`, but the Atlas API resolves the actual Customer, Site and Data Source from persisted records. A Connector cannot submit a different tenant identifier and thereby change scope.

Discovery remains evidence. It does not silently bypass the existing evidence/assertion/reconciliation boundary.

## 3.5 Decision E — technical discovery does not automatically invent business meaning

Technical Connectors may discover:

- Assets;
- Networks;
- Interfaces;
- technical relationships;
- status observations;
- facts and configuration; and
- optional service/application candidates.

They do not automatically create:

- Business Functions;
- business criticality;
- RTO/RPO values;
- owners;
- customer impact; or
- first-class Services solely because a container or process exists.

Atlas may later offer an assisted workflow such as “Promote Compose project to Service”, but that is a user decision.

## 3.6 Decision F — no time-series data warehouse inside Atlas

Connector implementations may submit current state and bounded facts such as CPU count, memory size, software version, current operational state and last boot time. They should not stream continuously changing telemetry such as CPU utilization every minute.

Time-series monitoring belongs in monitoring systems. Atlas may link to or correlate those systems later.

## 3.7 Decision G — Connector semantics are runtime-neutral

An Atlas Connector defines source meaning: identity rules, connection fields, discovery domains, source-to-AIP mappings, relationship semantics, collection dependencies, compatibility and trust metadata. It is not synonymous with an Ansible playbook or Collection.

The first implementation path is Ansible. A future runtime or standalone collector may implement the same Connector semantics if it produces the same AIP contract and passes the same fixtures/contract tests.

> **The architectural success criterion is that a competent contributor can connect a new source to Atlas without modifying Atlas domain code and, where a maintained Ansible Collection exists, without implementing the vendor API client.**

## 3.8 Decision H — collection-first source access

Before implementing source API code, a Connector author should evaluate the Ansible ecosystem in this order:

1. vendor-supported or Ansible-supported Collection;
2. mature Ansible community Collection;
3. vetted third-party Galaxy Collection;
4. small Atlas-owned source client isolated entirely behind the Connector/runtime boundary.

Atlas still owns the semantic mapping into AIP. A Collection may change its return schema or capabilities, so Connector fixtures and contract tests remain Atlas responsibilities. Collection versions are pinned and upgraded deliberately; Atlas never follows an unpinned `latest` dependency in a released Execution Environment.

## 3.9 Decision I — licensing boundary is architectural

Atlas core and the Ansible execution image are separate distributable/process components.

The target licensing posture is:

- Atlas core/AIP/SDK: permissive open-source licensing such as Apache-2.0, subject to the repository's formal licence decision;
- Ansible Runner and Ansible Builder: permissively licensed upstream components;
- `ansible-core`: GPL-3.0-or-later upstream component;
- Ansible Collections: licence recorded per exact collection/version; community Collections commonly use GPL-3.0-or-later;
- Atlas runtime-side code that directly imports/extends GPL Ansible internals, if ever required, stays on the runtime side and is released under a compatible licence.

Atlas core must not import GPL Ansible code. The runtime image must carry required notices, licence texts, SBOM/dependency provenance and corresponding-source obligations for components that require them. Commercial distribution should receive a final software-licensing review before release.

# 4. Target architecture

Target integration architecture — original exported diagram `assets/architecture-context.png` was not supplied.

## 4.1 Atlas control and knowledge plane

Atlas continues to own:

- authentication and authorization;
- Customer and Site context;
- integration catalogue;
- Connector semantics and trust tier;
- runtime registration/health;
- Integration-instance lifecycle;
- source credential lifecycle through `SecretProvider`;
- Connector, Execution Environment and collection compatibility/version policy;
- schedule intent and background run dispatch;
- DiscoveryRun lifecycle;
- ingestion authentication;
- payload validation;
- evidence persistence;
- entity/source identity;
- assertions and reconciliation;
- accepted Assets, Networks, Interfaces and relationships;
- Services, Business Functions and dependency semantics;
- graph and topology projections;
- changes, gaps and audit; and
- user-facing status and notifications.

## 4.2 Ansible execution plane

The isolated Atlas Ansible Runtime owns only execution concerns:

- invoke Ansible Runner;
- launch the selected pinned Execution Environment;
- expose bounded health/job-control APIs to Atlas;
- create an ephemeral job workspace;
- receive job-scoped secret material and callback token;
- run Connector playbooks/read-only discovery tasks;
- capture structured Runner events/artifacts;
- invoke the Connector normaliser over sanitised module results;
- validate AIP locally before submission;
- submit AIP batches to Atlas; and
- destroy ephemeral job inputs/secrets after completion.

The runtime does **not** own long-lived source credentials, Atlas tenancy, knowledge acceptance, or scheduling policy.

Ansible Runner is specifically intended to let other tooling invoke Ansible and consume structured results. Execution Environments provide a reproducible container boundary for `ansible-core`, Collections and Python dependencies. Atlas should build and release an immutable, pinned Execution Environment rather than installing arbitrary Collections dynamically into a production runtime.

## 4.3 Source systems and ecosystem reuse

Initial target systems remain:

- Proxmox VE;
- Docker Engine / Docker Compose; and
- UniFi Network.

The same architecture should later accommodate Cloudflare, Nginx Proxy Manager, Traefik, Uptime Kuma, Authentik, Synology, TrueNAS, Portainer, Kubernetes, Tailscale, Home Assistant and other systems without adding source-specific fields to the core Atlas `Integration` table.

For every new source, Atlas should first ask **“is there a maintained Ansible Collection that already handles authentication, API calls and version differences?”** If yes, Atlas should build only the thin playbook/normalisation semantics needed to produce AIP. If not, a direct source client remains permitted, but it must stay outside Atlas core and fail independently.

# 5. Logical component model

## 5.1 Integration Catalogue Service

The catalogue is Atlas-owned and is generated from versioned Connector manifests. A Connector manifest defines source semantics and declares the Ansible implementation/dependencies used to obtain observations.

Responsibilities:

- enumerate available official, platform-backed and community Connectors;
- validate Connector manifests and implementation descriptors;
- expose searchable catalogue metadata;
- show installed / available / incompatible state;
- validate minimum Atlas protocol, Connector and Execution Environment versions;
- report required Ansible Collections and trust/licence metadata;
- render Integration forms from manifest schemas; and
- expose Connector capabilities and source-access strategy to the web UI.

The initial catalogue is local and trusted. A remote community marketplace is explicitly deferred. Future community entries must identify publisher, trust tier, exact dependency versions, licence metadata and whether third-party executable code is required.

## 5.2 Integration Runtime Service

A backend abstraction isolates Atlas domain code from Ansible-specific implementation details.

```python
class IntegrationRuntime(Protocol):
    async def health(self) -> RuntimeHealth: ...
    async def inspect_capabilities(self) -> RuntimeCapabilities: ...
    async def ensure_connector(self, connector: ConnectorBundle) -> RuntimeConnectorState: ...
    async def test_connection(self, integration, job_secrets, run_token) -> ConnectionTestResult: ...
    async def run_discovery(self, integration, run, job_secrets, run_token) -> RuntimeJobRef: ...
    async def get_job(self, runtime_job_id: str) -> RuntimeJobStatus: ...
    async def cancel_job(self, runtime_job_id: str) -> None: ...
```

`AnsibleRuntime` is the only Community Preview implementation.

Scheduling is deliberately **not** a runtime API responsibility. Atlas stores schedule intent and its background worker creates normal DiscoveryRuns when schedules become due.

## 5.3 Integration Ingestion Service

A new Atlas API service accepts AIP v1 batches from runtime jobs.

Responsibilities:

- authenticate the run-scoped job token;
- load persisted run/integration/customer/site context;
- validate protocol, Connector and runtime/Execution Environment metadata;
- bound payload size and batch count;
- validate stable external identities;
- record evidence;
- update run-observed entities;
- resolve known source identities;
- create or update source-current assertions;
- create reconciliation items where required;
- update non-destructive observational facts;
- reconcile missing entities only after a successful complete snapshot; and
- update run counters and status.

## 5.4 Secret Provider Service

Atlas owns a `SecretProvider` abstraction.

Suggested interface:

```python
class SecretProvider(Protocol):
    async def create(self, scope, secret_fields) -> SecretReference: ...
    async def replace(self, ref, secret_fields) -> None: ...
    async def delete(self, ref) -> None: ...
    async def exists(self, ref) -> bool: ...
    async def materialize_for_job(self, ref, required_keys) -> JobSecretLease: ...
```

The default `AtlasEncryptedSecretProvider` stores only ciphertext and safe metadata in PostgreSQL. The encryption master key is not stored in PostgreSQL. `JobSecretLease` is short-lived and must be revoked/zeroised/deleted after job completion.

A future `OpenBaoSecretProvider` or equivalent external provider can implement the same interface.

## 5.5 Runtime token service

Each discovery run receives a short-lived, run-scoped credential to submit observations back to Atlas.

Recommended implementation:

- use a dedicated `INTEGRATION_RUN_SIGNING_KEY`, separate from the user session secret;
- issue a signed token with `aud=atlas-integration-ingest`;
- include `run_id`, `integration_id`, issued time, expiry and nonce/JTI;
- set a short expiry appropriate to the maximum Connector run duration;
- materialise the token only into the ephemeral runtime job; and
- never use this token for normal Atlas APIs.

A compromised job token therefore cannot read Atlas data or submit data for a different run.

# 6. Proposed data model

Proposed integration data model — original exported diagram `assets/data-model.png` was not supplied.

The proposed model is additive and intentionally reuses `Integration`, `DataSource`, `DiscoveryRun`, `EvidenceRecord`, `RunObservedEntity` and `EntitySourceLink`.

## 6.1 `integration_runtimes`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key. |
| `name` | string | Human-readable name, e.g. `Local Ansible Runtime`. |
| `runtime_type` | string | `ansible` in Community Preview. |
| `mode` | string | `local` initially; `remote` reserved. |
| `endpoint` | string/null | Only required for a separately hosted runtime service. |
| `execution_environment_ref` | string | Immutable image tag/digest or logical EE identifier. |
| `runtime_version` | string/null | Atlas Ansible Runtime version. |
| `ansible_runner_version` | string/null | Detected Runner version. |
| `ansible_core_version` | string/null | Version inside selected EE. |
| `collection_lock_digest` | string/null | Digest of the validated collection/dependency lock. |
| `status` | enum/string | `pending`, `connected`, `warning`, `unavailable`, `disabled`. |
| `capabilities_json` | JSON | Detected runtime/EE features. |
| `last_health_at` | datetime/null | Last health check. |
| `last_error` | text/null | Sanitised summary. |
| timestamps | datetime | Existing mixin convention. |

For the first Homelab release there is normally one instance-wide local runtime. Later MSP deployments may add remote/tenant-specific execution pools additively.

## 6.2 Evolve `integrations`

The current source-specific fields should be deprecated, not immediately dropped.

| Field | Purpose |
|---|---|
| `runtime_id` | Runtime that executes this Integration. |
| `connector_key` | Stable Atlas Connector key, e.g. `proxmox`, `docker`, `unifi`. |
| `connector_version` | Version of the Connector semantic contract. |
| `implementation_version` | Version of the Ansible playbook/normaliser implementation. |
| `data_source_id` | Explicit 1:1 provenance source for the Integration. |
| `credential_reference` | Opaque `SecretProvider` reference; never a secret value. |
| `config_json` | Non-secret Connector settings only. |
| `schedule_json` | Atlas-owned schedule configuration. |
| `enabled` | Allows disabling discovery without deleting history. |
| `last_test_at` / `last_test_status` | Connection validation summary. |
| `last_run_at` / `last_success_at` / `last_error_at` | Fast UI summary. |
| `runtime_metadata_json` | Safe EE/collection/runtime metadata used for the last run. |

Current `base_url`, `username_or_token_id`, `secret_reference` and `verify_tls` should remain during migration and then be removed in a deliberate later migration after live Integrations use the generic representation.

## 6.3 Secret records

The default encrypted provider may use a dedicated table with fields such as:

- secret UUID/reference;
- provider type;
- encrypted payload/ciphertext;
- nonce/associated encryption metadata required by the selected maintained library;
- key version identifier, but **not** the master key;
- safe field-name metadata only;
- created/rotated timestamps; and
- deleted/revoked state.

The exact cryptographic implementation belongs in a dedicated security ADR. Do not design custom cryptography in application code.

## 6.4 Connector/runtime implementation metadata

Official Connector manifests remain files in the repository/release bundle and are not database truth.

A small installed/runtime state record should track:

- runtime id;
- Connector key/version;
- implementation version;
- protocol version;
- Execution Environment image/digest;
- required Collection names and exact validated versions;
- collection lock digest;
- installed/validated time; and
- status/error.

## 6.5 Extend `discovery_runs`

Add:

- `connector_key`;
- `connector_version`;
- `implementation_version`;
- `protocol_version`;
- `runtime_id`;
- `runtime_job_id`;
- `execution_environment_ref`;
- `collection_lock_digest`;
- `trigger_type` (`manual`, `schedule`, `onboarding`, `retry`, later `webhook`);
- `requested_at`;
- `ingestion_started_at`;
- `last_batch_at`;
- `batch_count`;
- `observation_count`;
- `warning_count`; and
- optional sanitised runtime diagnostic reference.

Existing status, coverage, completeness, summary and error fields remain authoritative.

## 6.6 One Data Source per Integration instance

When an Integration is created, Atlas automatically creates or assigns its Data Source.

```text
Integration: Home Proxmox
Data Source: Home Proxmox / Proxmox VE
source_type: proxmox
trust_level: discovered
```

This removes ambiguity between a configured connection and its provenance identity.

## 6.7 Entity source identity remains multi-source

`EntitySourceLink` remains important because different Connectors can observe related or identical infrastructure.

Examples:

- UniFi may observe the MAC address and IP of a Proxmox host.
- Docker may run inside a Proxmox VM or LXC.
- Uptime Kuma may observe a service endpoint hosted by a Docker container.

Atlas must not assume each canonical Asset has only one source. Multiple external identities may map to one accepted Asset where reconciliation supports it.

# 7. Atlas Integration Protocol v1

## 7.1 Design goals

AIP v1 must be:

- runtime-independent;
- vendor-neutral;
- schema-versioned;
- batchable;
- idempotent;
- scope-safe;
- explicit about complete versus partial discovery;
- clear about observed versus inferred facts; and
- compatible with current evidence/reconciliation concepts.

## 7.2 Envelope

The connector submits batches to an endpoint conceptually equivalent to:

    POST /api/integration-ingest/runs/{run_id}/batches
    Authorization: Bearer <short-lived run token>

Illustrative payload:

    {
      "protocol_version": "1.0",
      "connector": {
        "key": "docker",
        "version": "1.0.0"
      },
      "integration_id": "67a...",
      "run_id": "a91...",
      "observed_at": "2026-09-25T04:20:00Z",
      "batch": {
        "sequence": 1,
        "final": false
      },
      "coverage": {
        "key": "docker-engine:2d8c...:inventory",
        "snapshot_mode": "full",
        "domains": ["assets", "networks", "interfaces", "relationships"]
      },
      "assets": [],
      "networks": [],
      "interfaces": [],
      "relationships": [],
      "service_candidates": [],
      "warnings": []
    }

Customer and Site identifiers are deliberately omitted. Atlas loads them from the persisted Integration and DiscoveryRun.

## 7.3 Stable source identifiers

Every object emitted by a connector implementation must have a stable source identifier that is not based solely on a mutable display name.

Examples:

| Connector | **Object**      | **Suggested external ID**                         |
|-----------|-----------------|---------------------------------------------------|
| Proxmox   | cluster         | `cluster/<cluster-name-or-stable-id>`             |
| Proxmox   | node            | `node/<node-name>`                                |
| Proxmox   | VM              | `qemu/<vmid>` or include cluster scope if needed  |
| Proxmox   | LXC             | `lxc/<vmid>`                                      |
| Proxmox   | storage         | `storage/<storage-id>`                            |
| Docker    | engine          | `engine/<docker-engine-id>`                       |
| Docker    | container       | `container/<container-id>`                        |
| Docker    | Compose project | `compose-project/<project-name>` scoped by engine |
| Docker    | network         | `network/<docker-network-id>`                     |
| Docker    | volume          | `volume/<volume-name-or-id>`                      |
| UniFi     | device          | `device/<device-id-or-mac>`                       |
| UniFi     | network         | `network/<network-id>`                            |
| UniFi     | site            | `site/<site-id>`                                  |

The Connector must document identity stability and collision scope; all runtime implementations of that Connector must preserve the same identity semantics.

## 7.4 Asset observation

    {
      "external_id": "container/9ab...",
      "asset_type": "docker_container",
      "name": "immich-server",
      "vendor": "Docker",
      "status": "active",
      "hostname": "immich-server",
      "description": null,
      "attributes": {
        "image": "ghcr.io/immich-app/immich-server:v2",
        "compose_project": "immich",
        "compose_service": "immich-server"
      },
      "facts": [
        {"key": "image", "value": "ghcr.io/...", "class": "configuration"},
        {"key": "state", "value": "running", "class": "operational"},
        {"key": "restart_policy", "value": "unless-stopped", "class": "configuration"}
      ]
    }

`class` guides retention and change semantics. Initial supported values:

- `identity` — stable identity-supporting fact;
- `configuration` — relevant configuration change;
- `operational` — current state, not necessarily a meaningful knowledge change; and
- `informational` — useful detail not normally used for reconciliation.

## 7.5 Network observation

    {
      "external_id": "network/4c2...",
      "name": "immich_default",
      "network_type": "docker_bridge",
      "vlan_id": null,
      "cidr": "172.23.0.0/16",
      "gateway": "172.23.0.1",
      "zone": null,
      "attributes": {"driver": "bridge"}
    }

Networks should become first-class Atlas `Network` records rather than generic Assets where a source genuinely represents a network or VLAN.

## 7.6 Interface observation

    {
      "asset_external_id": "container/9ab...",
      "external_id": "container/9ab.../network/4c2...",
      "name": "eth0",
      "network_external_id": "network/4c2...",
      "ip_address": "172.23.0.7",
      "mac_address": "02:42:ac:17:00:07",
      "is_primary": true
    }

Atlas should resolve `network_external_id` within the same source/run to a canonical Network before persisting the interface association.

## 7.7 Relationship observation

    {
      "source": {"kind": "asset", "external_id": "container/9ab..."},
      "target": {"kind": "asset", "external_id": "engine/2d8..."},
      "relationship_type": "runs_on",
      "truth_classification": "observed",
      "confidence": 1.0,
      "attributes": {}
    }

Valid truth classifications align with Atlas:

- `observed`;
- `inferred`.

declared and intended remain Atlas/user concepts and should not normally be emitted by technical Connector implementations.

## 7.8 Service candidates

Connector implementations may emit a non-authoritative candidate hint without creating a Service:

    {
      "external_id": "compose-project/immich",
      "name": "Immich",
      "candidate_type": "application_service",
      "supported_by": ["compose-project/immich"],
      "reason": "Docker Compose project with externally published application containers"
    }

The UI can later show “Create Service from candidate”. This is optional for v1 and may be excluded from the first implementation if it threatens release scope.

## 7.9 Run completion

A run is complete only when the connector implementation explicitly submits a completion call:

    POST /api/integration-ingest/runs/{run_id}/complete

with:

- completeness (`complete`, `partial`, `failed`);
- coverage key(s);
- counts;
- warnings;
- connector summary; and
- optional source version/capability summary.

Atlas must never perform no-longer-observed reconciliation from a failed or partial snapshot.

# 8. Provenance, acceptance and reconciliation

## 8.1 Core rule

**Observed source state is not automatically the same as accepted Atlas knowledge.**

The integration subsystem must preserve the existing Atlas distinction between evidence, assertions, reconciliation and accepted operational records.

## 8.2 Initial discovery usability

A strict review-every-field workflow would be too cumbersome for homelab onboarding. The recommended first-run behaviour is:

1.  run discovery;
2.  show a grouped import summary;
3.  allow **Accept all new** for genuinely new objects and relationships;
4.  show possible duplicates separately;
5.  show conflicting changes separately; and
6.  never automatically interpret absence until a complete baseline has been established.

This preserves user agency while still allowing a 40–100 object environment to be imported quickly.

## 8.3 Subsequent runs

Subsequent complete runs should distinguish:

- unchanged observations;
- operational-state updates;
- material configuration changes;
- new entities;
- new relationships;
- changed identities;
- possible duplicates; and
- no-longer-observed entities.

Non-destructive current-state facts may update automatically where they are explicitly classified as operational. Changes to accepted identity/configuration fields should follow the existing assertion/reconciliation path unless the user has enabled a future trusted auto-accept policy.

## 8.4 Integration trust policy

Design the schema now, but implement only the first two modes initially:

- `review` — all material knowledge changes require acceptance;
- `auto_accept_new` — new unambiguous entities/relationships can be accepted after the user explicitly enables this policy; conflicts/removals remain review items;
- `trusted_source` — future mode for selectively authoritative fields.

Default for a newly created integration should be `review`. Guided Homelab onboarding may offer `auto_accept_new` with an explanation.

# 9. Connector and runtime implementation package specification

Connector package structure — original exported diagram `assets/adapter-package.png` was not supplied.

## 9.1 Repository structure

Recommended structure:

```text
integrations/
  protocol/
    atlas-integration-protocol-v1.schema.json
    connector-manifest-v1.schema.json
  shared/
    python/
      atlas_integration_sdk/
        models.py
        validation.py
        submit.py
        redaction.py
  execution_environments/
    infrastructure/
      execution-environment.yml
      requirements.yml
      requirements.txt
      lock.json
  connectors/
    proxmox/
      atlas.connector.yaml
      README.md
      CHANGELOG.md
      semantics/
        identity.md
        mappings.py
      implementations/
        ansible/
          playbooks/
            test_connection.yml
            discover.yml
          normalizer.py
          requirements.yml
          fixtures/
          tests/
    docker/
      ...
    unifi/
      ...
```

This can coexist temporarily with `plugins/sdk` and `plugins/proxmox`. Migration should reuse existing tests and semantic mapping rather than deleting them first.

## 9.2 Connector manifest

Illustrative manifest:

```yaml
api_version: atlas.integrations/v1
kind: Connector
metadata:
  key: proxmox
  name: Proxmox VE
  version: 1.0.0
  publisher: atlas
  channel: official
  category: virtualisation
  description: Discover Proxmox clusters, nodes, guests, storage and networking.

compatibility:
  atlas_protocol: "1.0"
  minimum_atlas_version: "0.1.0"

capabilities:
  test_connection: true
  run_now: true
  scheduled_discovery: true
  complete_snapshot: true
  domains: [assets, networks, interfaces, relationships]

connection_form:
  fields:
    - key: endpoint
      label: Proxmox endpoint
      type: url
      required: true
    - key: token_id
      label: API token ID
      type: string
      required: true
    - key: token_secret
      label: API token secret
      type: secret
      required: true
    - key: tls_mode
      label: TLS validation
      type: enum
      values: [verify, fingerprint, insecure]
      default: verify

implementations:
  - runtime: ansible
    version: 1.0.0
    playbook: implementations/ansible/playbooks/discover.yml
    test_playbook: implementations/ansible/playbooks/test_connection.yml
    normalizer: implementations/ansible/normalizer.py
    execution_environment: atlas-infra-ee
    collections:
      - name: community.proxmox
        version_from_lock: true

outputs:
  asset_types:
    - proxmox_cluster
    - hypervisor_node
    - virtual_machine
    - container
    - storage_pool
    - network_bridge
  relationship_types:
    - contains
    - member_of
    - runs_on
    - uses_storage
    - connected_to
```

The manifest drives Atlas UI/validation and identifies the collection dependencies used by the Connector. Runtime code must not invent additional secret fields at execution time.

## 9.3 Ansible implementation rules

An official Ansible Connector implementation should consist of thin, read-only playbooks plus a deterministic normaliser. The playbook obtains facts using pinned Collections. The normaliser converts sanitised source/module results to AIP without importing Ansible internals.

Do not create custom Ansible callback/plugins merely to transport data unless standard Runner job events/artifacts cannot meet the requirement. If runtime-side code must directly import GPL Ansible internals, keep that code in the separately licensed runtime component.

## 9.4 Execution Environment and dependency lock

Released Atlas versions use immutable Execution Environments. The build should pin:

- `ansible-core` version;
- `ansible-runner` compatibility requirement;
- every Collection name/version;
- Python dependencies required by those Collections; and
- image base/digest where practical.

Use Ansible Builder or equivalent reproducible build tooling. CI should emit an SBOM, dependency/licence manifest and collection lock digest. Runtime startup verifies that the selected EE is compatible with the Atlas release and Connector manifest.

Atlas must never run `ansible-galaxy collection install --upgrade` against an unpinned production environment.

## 9.5 Credential convention

Connector secret fields are persisted only through `SecretProvider`.

At job start Atlas leases only the required secrets to the runtime. The runtime materialises them into an ephemeral job directory or environment with restrictive permissions, marks secret-bearing tasks/values `no_log` where applicable, prevents secret values entering returned AIP/artifacts, and destroys the material after completion.

The Integration record stores only `credential_reference` and safe configuration. Deleting credentials must not delete discovery history or accepted Assets.

# 10. Operational flows

Discovery run lifecycle — original exported diagram `assets/run-lifecycle.png` was not supplied.

## 10.1 Configure/validate runtime

For the Homelab profile the local Ansible runtime should normally be deployed automatically with the Atlas stack or enabled as an installation profile.

1. Atlas checks the `atlas-ansible-runtime` health endpoint.
2. Runtime reports its version and selected Execution Environment digest.
3. Runtime reports detected `ansible-runner`, `ansible-core` and collection-lock metadata.
4. Atlas verifies protocol/runtime compatibility.
5. Runtime status becomes Connected/Healthy.

A future remote runtime may add endpoint authentication, but Community Preview should not require a separate Ansible UI, workspace or API token configuration step for the normal local deployment.

## 10.2 Prepare Connector implementation

1. User opens Integration Catalogue.
2. Atlas loads the local official Connector manifest.
3. Compatibility is evaluated against Atlas/AIP/runtime/EE/collection lock.
4. User selects Configure.
5. Atlas verifies that the selected immutable EE contains the Connector's required Collection set.
6. Atlas records implementation/EE/collection metadata.
7. No dynamic unpinned package installation is performed in the production runtime.

## 10.3 Create Integration instance

1. User selects Customer/Site context.
2. User enters a name and Connector-specific fields.
3. Atlas validates non-secret fields.
4. Atlas sends secret fields to `SecretProvider` and stores only the returned opaque reference.
5. Atlas creates a Data Source.
6. Atlas optionally runs Test Connection.
7. Integration status becomes Ready or Needs attention.

## 10.4 Test Connection

Test Connection should be synchronous from the user's perspective and bounded, normally under 30 seconds.

Atlas creates a short-lived runtime job with a secret lease and sanitised configuration. The Connector's Ansible test playbook runs against the source and returns only safe capability information.

```json
{
  "valid": true,
  "message": "Connected to Proxmox VE",
  "details": {
    "version": "9.x",
    "cluster_name": "homelab",
    "nodes_visible": 3
  }
}
```

No credential value, authorization header, SSH private key or secret-bearing module argument may appear in Atlas responses or retained runtime artifacts.

## 10.5 Run Now

1. Atlas authorizes `integrations.run` against the Integration scope.
2. Atlas creates `DiscoveryRun(status=pending)`.
3. Atlas generates a run-scoped ingestion token.
4. Atlas leases the Integration credentials from `SecretProvider` for this job.
5. Atlas background orchestration calls `AnsibleRuntime.run_discovery` asynchronously.
6. Runtime creates an isolated Runner job using the pinned EE.
7. Ansible Collection modules/plugins query the source read-only.
8. Runtime normalises results and posts validated AIP batches.
9. Atlas records evidence/reconciliation.
10. Runtime submits final completion/failure summary.
11. Atlas closes the run and revokes/destroys the credential lease/job material.

## 10.6 Scheduled discovery

Atlas owns schedule intent **and execution timing**.

When a schedule becomes due:

1. Atlas worker/scheduler creates a normal DiscoveryRun;
2. it follows the same run-scoped token/secret lease path as Run Now;
3. it dispatches to the configured runtime;
4. retries are applied according to Atlas policy; and
5. all executions share the same audit/provenance lifecycle.

Ansible itself is not the source of schedule truth.

## 10.7 Runtime unavailable

If the Ansible runtime is unavailable:

- existing Atlas knowledge remains readable;
- graphs and topology continue to work;
- manual knowledge remains usable;
- Integrations show Runtime unavailable;
- new discovery jobs cannot start;
- no Assets are marked stale merely because the runtime is offline; and
- Atlas retries runtime health checks independently of discovery.

## 10.8 Disable Integration

Disabling an Integration:

- prevents scheduled and manual runs;
- preserves safe configuration and credentials unless the user chooses otherwise;
- preserves Data Sources, Runs, Evidence, Source Links and accepted knowledge; and
- does not mark source entities absent.

## 10.9 Delete Integration

Deletion should be a deliberate lifecycle action with strong confirmation.

Recommended default is **Archive/Remove connection**, not destructive purge.

Options:

- disable future runs;
- delete the credential reference/value;
- retain Atlas run/evidence/provenance history;
- retain accepted Assets and relationships; and
- retain source links as historical provenance or end them according to a future source-link lifecycle field.

# 11. Atlas UI design

The integration UI should reuse the existing Atlas design system and current shell. Do not create a separate “automation product” visual style.

UI implementation should reuse existing primitives where possible:

- `PageHeader`;
- status badges;
- table cards;
- filter bars;
- dialog cards;
- existing permission checks;
- Customer/Site workspace context; and
- user accent/theme tokens.

The CSS should use Atlas theme variables rather than hard-coded blue; the mock-ups below use the current screenshot’s blue accent for illustration.

## 11.1 Integrations overview

![Proposed configured integrations screen](../../architecture/integrations/assets/integrations-overview.png)


Recommended page structure:

- header: Connections / Integrations;
- primary action: Add integration;
- tabs: Configured, Catalogue, Runtime;
- compact status cards: Runtime, Configured count, last-24-hour runs, attention count;
- configured integration table.

Columns:

- Integration;
- Connector;
- Scope;
- Schedule;
- Last run;
- Status;
- actions.

Do not show raw secret references. Endpoint display is Connector-controlled safe metadata.

### Status vocabulary

Use a small stable status set:

- `Ready` / `Healthy`;
- `Running`;
- `Needs attention`;
- `Disabled`;
- `Runtime unavailable`;
- `Upgrade available`.

Avoid conflating source operational status with integration connection status.

## 11.2 Catalogue

![Proposed integration catalogue](../../architecture/integrations/assets/connector-catalogue.png)


Connector catalogue cards show:

- Connector icon/name;
- category;
- one-sentence discovery scope;
- publisher and trust tier (Atlas Official / Platform-backed / Community / Local);
- installed/available/roadmap state;
- optional minimum-version warning; and
- Configure action.

Initial categories:

- Virtualisation;
- Containers;
- Networking;
- Edge / DNS;
- Monitoring;
- Identity;
- Storage / Backup.

## 11.3 Add Integration wizard

![Proposed Proxmox connection wizard](../../architecture/integrations/assets/add-proxmox-wizard.png)


Wizard stages:

1.  **Scope** — Customer and Site, defaulted from active Atlas context.
2.  **Connection** — manifest-generated fields.
3.  **Test** — run connection test and display capabilities.
4.  **Discovery** — object domains, optional filters, cadence, trust policy.
5.  **Review** — safe summary and Create + Run initial discovery.

### Form generation

The Connector manifest should define field types so Atlas can generate standard forms:

- text;
- URL;
- integer;
- boolean;
- enum;
- secret/password;
- PEM/multiline secret;
- asset selector;
- network selector; and
- advanced JSON only for developer/community Connectors later.

Secret fields are never re-populated after save. Edit shows `Configured` and provides Replace/Clear controls.

## 11.4 Integration detail

![Proposed integration detail screen](../../architecture/integrations/assets/integration-detail.png)


The integration detail page should provide:

### Header

- integration name;
- Connector and scope;
- health badge;
- Test Connection;
- Run Now;
- menu for Edit, Disable, Upgrade Connector implementation, Remove connection.

### Summary

- last successful run;
- next scheduled run;
- discovered coverage summary;
- Connector version / implementation version.

### Tabs

- Overview;
- Configuration;
- Discovery;
- Runs;
- Data coverage.

The normal user should not need to open the execution runtime. An Advanced section may provide “Open runtime job” if a safe runtime-specific link can be generated.

## 11.5 Runtime settings

![Proposed Integration Runtime settings](../../architecture/integrations/assets/runtime-settings.png)

Location: **System Settings → Integration Runtime** or the Runtime tab under Integrations. The visual layout can remain as shown, but the fields/status are Ansible-specific. The normal Homelab user should not need to configure or open Ansible directly.

Fields:

- Runtime name;
- Runtime type (`Ansible`);
- mode (`Local` initially; `Remote` reserved);
- Execution Environment image/digest;
- credential provider status; and
- optional remote endpoint/TLS settings only when remote mode is enabled.

Health area:

- Atlas Ansible Runtime API;
- runtime version;
- `ansible-runner` version;
- `ansible-core` version;
- Execution Environment digest;
- collection-lock status;
- queued/running jobs if exposed; and
- last health error.

## 11.6 Discovery run detail

Extend the existing Discovery Runs UI rather than duplicate it under Integrations.

A run detail should show:

- Integration, Connector version and runtime implementation version;
- trigger type;
- Atlas Run ID and Ansible Runtime Job ID;
- start/finish/duration;
- complete/partial snapshot state;
- coverage key;
- counts by domain;
- new/changed/unchanged/no-longer-observed counts;
- reconciliation items created;
- warnings;
- sanitised failure;
- batches received; and
- links to Changes/Reconciliation filtered to the run.

# 12. Guided onboarding

Proposed guided setup — original exported diagram `assets/ui-onboarding.png` was not supplied.


## 12.1 Setup profile

Initial options:

### Personal / Homelab — recommended default

- one initial Customer and Site;
- simplified language;
- capabilities can be labelled “Capabilities” in UI while retaining Business Function storage;
- discovery-first setup;
- optional single local administrator;
- suggested Proxmox, Docker and UniFi Connectors.

### Organisation

- Customer/Site naming appropriate for the business;
- multi-user administration visible;
- formal Services and Business Functions retained;
- discovery plus manual knowledge workflows.

### Managed Environments

Show as a later/advanced profile if MSP functions are not yet complete. Do not promise cross-customer fleet management before it exists.

## 12.2 Homelab onboarding sequence

1.  Welcome and profile selection.
2.  Name environment: Customer and Site.
3.  Integration runtime:
    - Validate the local Ansible runtime (normally automatic); or
    - Skip integrations and use Atlas manually.
4.  Connector selection:
    - Proxmox VE;
    - Docker + Compose;
    - UniFi Network.
5.  Configure each Connector.
6.  Test connections.
7.  Run initial discovery.
8.  Review discovered items:
    - Accept all new;
    - review duplicates/conflicts;
    - defer optional items.
9.  Open generated topology.
10. Completion card explaining where to manage integrations and discovery.

## 12.3 Resume behaviour

Onboarding must be resumable. Persist completed setup steps in Atlas System Settings or a dedicated setup-state record. A browser refresh must not require starting again.

# 13. Reference connector — Proxmox VE

## 13.1 Existing code to reuse

Current `plugins/proxmox` already provides:

- HTTPS/API token validation;
- node discovery;
- QEMU discovery;
- LXC discovery;
- storage discovery;
- bridge discovery;
- vendor-neutral normalization; and
- unit tests.

Reuse the existing implementation as a semantic/test reference while moving production source access toward the pinned `community.proxmox` Collection. At the time of this design, `community.proxmox` provides a Proxmox inventory plugin and a growing module set. Build a capability matrix before deleting existing source-access code; any temporary direct-API fallback must remain isolated inside the Connector runtime implementation. Do not maintain two long-lived production Proxmox clients.

## 13.2 Connection fields

| **Field**               | **Type** | **Secret** | **Notes**                                                                |
|-------------------------|----------|------------|--------------------------------------------------------------------------|
| Name                    | text     | No         | Atlas Integration name.                                                  |
| Endpoint                | URL      | No         | `https://host:8006`.                                                     |
| Token ID                | text     | No         | Dedicated API token identity.                                            |
| Token secret            | secret   | Yes        | Stored through Atlas `SecretProvider`; leased to the runtime per job.   |
| TLS mode                | enum     | No         | `verify`, `fingerprint`, `insecure`; insecure requires explicit warning. |
| Certificate fingerprint | text     | No         | Required in fingerprint mode.                                            |
| Discovery scope         | enum     | No         | Cluster/all visible resources initially.                                 |
| Include templates       | boolean  | No         | Default false or separate class depending product choice.                |

## 13.3 Discovery domains

### Cluster

Add Proxmox cluster discovery. Proxmox clusters are important operational entities because node membership, quorum and shared configuration exist at cluster scope.

Canonical mapping:

| **Source concept** | **Atlas representation**                                                                |
|--------------------|-----------------------------------------------------------------------------------------|
| Proxmox Cluster    | Asset type `proxmox_cluster`                                                            |
| Proxmox Node       | Asset type `hypervisor_node` (retain current mapping initially)                         |
| QEMU guest         | `virtual_machine`                                                                       |
| LXC guest          | `container` initially for compatibility; consider managed display label `LXC Container` |
| Storage            | `storage_pool`                                                                          |
| Linux bridge       | `network_bridge` Asset initially; richer Network mapping later                          |

Relationships:

    Proxmox Cluster --contains--> Node
    Node --member_of--> Proxmox Cluster   (choose one canonical direction; do not persist both)
    VM/LXC --runs_on--> Node
    Node --uses_storage--> Storage Pool
    Bridge --connected_to--> Node

Persist one semantic edge, not redundant inverse rows. UI inverse labels come from Relationship Type definitions.

## 13.4 Cluster and standalone mode

The same Connector implementation must support:

- standalone Proxmox node;
- 2-node/3-node/multi-node cluster.

If no cluster exists, do not manufacture a synthetic cluster unless a later UI grouping feature needs a presentation-only root.

## 13.5 Optional second-stage detail

After the existing inventory path is reliable, add bounded detail discovery for:

- guest network interfaces;
- VLAN tags and bridge attachment;
- node management interface;
- HA-managed guest state;
- pools/tags;
- backup job references if deliberately included later.

This second stage should not block the initial integration release.

## 13.6 Coverage keys

Examples:

    proxmox:<integration-id>:inventory
    proxmox:<integration-id>:network-detail

Only a complete `inventory` snapshot should drive missing-entity detection for the inventory objects in its domain.

# 14. Reference connector — Docker and Docker Compose

## 14.1 Why Docker is release-critical

Proxmox shows where compute runs; Docker shows the applications the homelab operator actually recognizes. For community adoption, Docker/Compose is therefore as important as Proxmox.

## 14.2 Supported connection modes

Design for three modes, but implement a safe subset first.

### SSH — recommended homelab remote mode

Docker source access should prefer the pinned `community.docker` Collection. For remote engines, SSH is the recommended Homelab mode where supported by the selected Collection/CLI path. The SSH credential is stored through Atlas `SecretProvider` and leased only to the isolated job.

### TLS-protected Docker Engine API

For operators with a remote Docker Engine API, require authenticated TLS. Docker’s documentation warns that insecure remote daemon access can grant host-level control and should not be exposed without appropriate protection.

### Local Unix socket — advanced

Only available when the dedicated Atlas Ansible Runtime/Execution Environment has been explicitly granted access to the target Docker socket. This should be labelled advanced because Docker socket access is effectively host-level privilege.

Do **not** recommend plain unauthenticated `tcp://host:2375`.

## 14.3 Connection fields

Common:

- name;
- connection mode;
- engine endpoint/host;
- TLS verification; and
- optional parent Atlas Asset.

SSH fields:

- hostname;
- port;
- username;
- private key stored through Atlas `SecretProvider`;
- optional known-host fingerprint.

TLS fields:

- Docker API URL;
- CA certificate;
- client certificate;
- client private key.

## 14.4 Parent infrastructure mapping

Docker frequently runs inside a Proxmox VM or LXC. During setup, Atlas should offer:

> **Runs on (optional):** select the VM/LXC/physical server hosting this Docker Engine.

This is an asserted relationship supplied by the operator and avoids unreliable hostname-only merging.

Recommended model:

    Docker Engine Asset --runs_on--> Proxmox VM/LXC/Physical Server
    Container --runs_on--> Docker Engine Asset
    Compose Project --runs_on--> Docker Engine Asset
    Compose Project --contains--> Container

Do not merge the Docker Engine and its underlying VM/LXC into one Asset; they are different operational layers.

## 14.5 Docker asset mappings

| **Docker concept** | **Atlas mapping**                                                        |
|--------------------|--------------------------------------------------------------------------|
| Docker Engine      | `docker_host` Asset                                                      |
| Compose Project    | new managed type `application_stack` or `compose_project` under Software |
| Container          | `docker_container` Asset                                                 |
| Image              | fact on container in v1; separate entity deferred                        |
| Docker network     | Atlas `Network`, `docker_bridge` / `overlay` type                        |
| Named volume       | optional `storage_volume` Asset or fact in v1                            |
| Bind mount         | fact/relationship hint; avoid manufacturing filesystem Assets initially  |

## 14.6 Compose detection

Docker Compose applies canonical labels such as `com.docker.compose.project` and `com.docker.compose.service`. Use these observed labels to group running containers into a Compose Project.

Compose project identity should be scoped by Docker Engine because identical project names can exist on different engines.

Recommended external ID:

    compose-project/<engine-id>/<project-name>

## 14.7 Networks and interfaces

For each Docker network:

- create/update an Atlas Network;
- record driver, scope and relevant labels as facts;
- capture subnet/gateway where available.

For each container-network attachment:

- create/update an AssetInterface;
- use network endpoint IP/MAC;
- associate the interface with the canonical Network.

This directly improves Atlas’s Network/VLAN and connectivity views.

## 14.8 Port publishing

Published ports are configuration facts in v1:

    container.publish.tcp.2283 = 0.0.0.0:2283

Do not automatically claim internet exposure based solely on a published Docker port. Later Cloudflare/proxy/firewall Connectors can establish a complete exposure path.

## 14.9 Volumes

V1 should discover:

- named volume identity;
- mount destination;
- read/write mode;
- Compose project labels where present.

The product can initially keep named volumes as storage facts. Promote them to Assets only when needed for topology/recovery analysis. Avoid exploding a homelab graph with every ephemeral anonymous volume.

## 14.10 Noise controls

Default exclusions:

- stopped containers older than configurable retention;
- one-off Compose task containers;
- anonymous volumes;
- transient build containers;
- image layers;
- swarm objects unless Swarm support is explicitly enabled.

The Connector manifest should expose sensible filters rather than requiring users to write arbitrary queries.

# 15. Reference connector — UniFi Network

## 15.1 Role in Atlas

UniFi provides network truth that Proxmox and Docker cannot reliably infer:

- gateways;
- switches;
- access points;
- Networks/VLANs;
- device management addresses;
- connected client observations; and
- potentially physical/uplink relationships when exposed by the supported API.

The official UniFi Network APIs expose sites, adopted devices, device details/statistics, connected clients and Networks. Atlas should first evaluate maintained Ansible Galaxy Collections for this read-only discovery scope. Third-party Collections must be vetted for maintenance, licence, permissions and output stability before inclusion in the default EE. If no sufficiently mature Collection covers the required discovery, use a small Atlas-owned read-only source client or `ansible.builtin.uri` playbook isolated entirely inside the runtime. Never depend on unsupported controller database access.

## 15.2 Connection modes

### Local UniFi Network application — initial priority

Best fit for homelabs. Connection fields:

- controller/application URL;
- API key;
- local site selector after Test Connection;
- TLS mode.

### UniFi Site Manager cloud — future/optional

Useful for multi-site business/MSP usage where the operator wants one cloud API connection. Treat as a separate connection mode or Connector implementation variant because scope and endpoints differ.

## 15.3 Mapping

| **UniFi concept**         | **Atlas mapping**                                             |
|---------------------------|---------------------------------------------------------------|
| Gateway                   | `firewall` or `router` according to model/function            |
| Switch                    | `switch`                                                      |
| Access point              | `access_point`                                                |
| Network/VLAN              | Atlas `Network` with `vlan_id`, CIDR, gateway where available |
| Controller/application    | optional `network_controller` Asset or integration metadata   |
| Device management address | AssetInterface                                                |
| Connected client          | observation; do not auto-create every client Asset by default |

## 15.4 Physical topology

If the documented API response provides a reliable device uplink/neighbor identifier, create:

    Access Point --uplinks_to--> Switch
    Access Switch --uplinks_to--> Distribution Switch
    Switch --uplinks_to--> Gateway

If the supported API does not provide reliable uplink identity, do **not** infer it from names or IP ranges. Atlas may show device and network membership without manufacturing a physical link.

## 15.5 Client observations

Connected clients can be noisy. Default policy:

- record client observations as evidence;
- if MAC address maps unambiguously to an existing Atlas AssetInterface, enrich/link the existing Asset;
- do not create every phone, TV or temporary guest as an Atlas Asset by default;
- offer `Import network clients` as an advanced opt-in discovery scope.

This gives UniFi useful identity correlation without turning Atlas into a client tracker.

## 15.6 Networks/VLANs

UniFi Networks should become canonical Atlas Network records where accepted.

Example:

    Name: IoT
    network_type: vlan
    vlan_id: 30
    cidr: 192.168.30.0/24
    zone: iot
    source: UniFi

Known infrastructure AssetInterfaces can then belong to these Networks, improving the existing topology view.

# 16. Connector developer workflow

## 16.1 Create a new Connector

A contributor should be able to connect a new source without understanding Atlas ORM internals and without modifying Atlas domain code.

Workflow:

1. Copy `integrations/connectors/_template`.
2. Choose a stable Connector key and semantic version.
3. Define the runtime-neutral manifest and connection form.
4. Search Ansible Galaxy/vendor Collections for existing source support.
5. Record candidate Collection publisher, licence, release activity, permissions, exact validated version and required Python dependencies.
6. Choose the source-access strategy: trusted Collection, vetted third-party Collection, or isolated Atlas fallback.
7. Implement `test_connection.yml` and read-only discovery playbook(s).
8. Implement deterministic source-result → AIP normalisation outside Ansible internals.
9. Validate AIP locally.
10. Add sanitised fixtures and contract tests.
11. Prove idempotency and complete/partial snapshot handling.
12. Test against the pinned Execution Environment.
13. Run against an Atlas test Integration.
14. Document required source permissions and data collected.
15. Update the collection/dependency lock only through reviewed CI/build workflow.

## 16.2 Connector implementation coding rules

Every Connector implementation must:

- be read-only unless a future manifest explicitly declares otherwise;
- use stable external IDs;
- use maintained Collection modules/plugins where practical;
- paginate/bound source queries where the source requires it;
- set timeouts and bound concurrency;
- sanitise errors;
- never log secrets;
- declare complete versus partial discovery truthfully;
- distinguish observed from inferred relationships;
- avoid transient high-volume objects by default;
- not choose Customer or Site;
- not call Atlas APIs other than the supplied AIP/run endpoints;
- remain idempotent for the same source state; and
- fail independently without taking Atlas core down.

## 16.3 Connector contract tests

The shared test suite should verify:

- manifest schema;
- secret fields never appear in logs/results/fixtures;
- stable external IDs;
- duplicate external IDs rejected;
- relationships reference valid entities;
- network references resolve;
- complete/partial semantics;
- deterministic fixture normalisation;
- source/Collection errors are sanitised;
- no source credential is present in AIP output;
- payload respects size limits;
- supported AIP version;
- supported EE/collection lock;
- repeated unchanged discovery is quiet/idempotent; and
- a Connector failure cannot crash Atlas API/worker processes.

## 16.4 Collection selection policy

A Collection is not trusted merely because it exists on Galaxy. Before Atlas includes it in the default EE, record:

- publisher/namespace;
- licence and notices;
- source repository;
- maintenance/release activity;
- supported `ansible-core` versions;
- required privileges;
- dependency tree;
- whether it uses documented vendor APIs;
- exact version/digest validated by Atlas; and
- replacement/fallback plan if it becomes unmaintained.

# 17. Security design

## 17.1 Trust boundaries

There are five primary security domains:

1. browser/user → Atlas;
2. Atlas → `SecretProvider` / encrypted secret storage;
3. Atlas worker/API → Atlas Ansible Runtime;
4. Ansible Runtime/Execution Environment → source system; and
5. runtime job → Atlas AIP ingestion endpoint.

Treat each separately.

## 17.2 Atlas to runtime

For the default local deployment, expose the runtime only on an internal container/network boundary where practical. If a remote runtime mode is added, use a narrowly scoped service credential and TLS/mTLS appropriate to the deployment.

The runtime API should permit only:

- health/capability inspection;
- start a validated Connector job;
- get/cancel that job; and
- no general-purpose arbitrary playbook execution from the browser.

## 17.3 Source credentials

Source credentials are persisted through Atlas `SecretProvider` and are write-only from the UI.

Audit events should record:

```text
Integration credentials updated
Connector: Proxmox
Integration: Home Proxmox
Actor: <user>
```

but never credential values or full submitted fields.

The default encrypted provider must use maintained cryptographic primitives/libraries, keep the master key outside the database and support key-version metadata/rotation. Do not invent cryptographic algorithms or custom ciphers.

## 17.4 Job secret materialisation

A discovery job receives only the credentials it needs. Secret material must be:

- scoped to the job;
- exposed to the runtime through an ephemeral directory/file/environment mechanism with restrictive permissions;
- excluded from retained job arguments and AIP payloads;
- protected with Ansible `no_log` where tasks could echo secret-bearing values;
- redacted from exceptions/stdout/event artifacts; and
- destroyed/revoked after success, failure or cancellation.

## 17.5 Run callback authentication

Use run-scoped signed tokens as described earlier. Ingestion endpoints must additionally verify:

- run exists;
- run belongs to Integration;
- run is pending/running;
- token Integration/run claims match;
- Connector/version metadata match expected run metadata;
- run is not archived/cancelled/expired; and
- payload sequence is valid.

## 17.6 URL and SSRF considerations

Atlas deliberately connects to internal infrastructure, so blanket blocking private IP ranges would break the product.

Mitigations instead include:

- trusted official Connectors/Collections in the initial catalogue;
- strict schemes per Connector (`https`, SSH where required);
- reject embedded URL credentials;
- disable or tightly control redirects;
- source-specific URL validation;
- timeout and response-size limits;
- TLS verification by default; and
- no generic arbitrary HTTP Connector exposed to ordinary users in v1.

## 17.7 Runtime and Execution Environment isolation

- Atlas core never imports `ansible-core`.
- Discovery executes in a separate process/container boundary.
- Prefer immutable read-only EE images plus an ephemeral writable job workspace.
- Do not mount the Docker socket except for an explicitly configured advanced Docker discovery mode.
- Do not mount the Atlas database socket/data directory into the runtime.
- Give the runtime no general Atlas user/session credentials.
- Bound CPU/memory/runtime where practical.

## 17.8 Data minimisation

Connector implementations should collect only data that contributes to inventory, relationship, change or operational context. Do not ingest:

- application payload content;
- user document contents;
- passwords;
- arbitrary environment variable values;
- container secrets;
- Wi-Fi client browsing data; or
- raw log streams.

Environment variable names may be useful in limited cases, but values should be excluded by default.

## 17.9 Third-party Collection supply chain

Atlas must not silently install or upgrade arbitrary Galaxy content. The default EE contains only reviewed, pinned dependencies. Connector metadata/lock data should record publisher, exact version, source repository, licence and integrity information where practical.

Community/admin-supplied Collections are a future advanced feature and require an explicit trust decision plus isolation. A compromised Collection executes code with the runtime's source/network privileges.

## 17.10 Licensing and redistribution controls

CI/release engineering should generate an SBOM and licence inventory for Atlas core and the runtime image separately. Preserve upstream copyright/licence notices and corresponding-source obligations for GPL components distributed in the runtime image.

The separate-container boundary is deliberate for both security and licensing clarity. It is not a substitute for legal review: before a paid/commercial distribution, review the exact binaries/images, modifications and distribution method with software-licensing counsel.

# 18. Scheduling, jobs and operational status

## 18.1 Scheduling strategy

Atlas executes schedules through its background worker. The Ansible runtime is an execution target, not a scheduler.

Initial schedule presets:

- Manual only;
- Every 15 minutes;
- Every 30 minutes;
- Hourly;
- Every 6 hours;
- Daily;
- Custom cron (advanced).

Use source-appropriate defaults:

- Proxmox: every 30 minutes;
- Docker: every 15 or 30 minutes;
- UniFi: every 30 or 60 minutes.

## 18.2 Retry policy

Retries should distinguish:

- source authentication failure — no automatic repeated retry storm;
- connection timeout — small bounded retry;
- rate limit — backoff where source gives retry information;
- runtime unavailable — bounded infrastructure retry without marking source entities absent;
- Atlas ingestion temporary error — retry batch safely using idempotency key;
- AIP validation/schema error — fail immediately because retry will not fix code; and
- Collection/module compatibility error — fail Connector clearly and preserve last-known-good Atlas knowledge.

## 18.3 Idempotent batches

Each batch should include a deterministic idempotency key derived from run + sequence. Atlas stores received sequence numbers or batch hashes so the runtime can retry submission without duplicate EvidenceRecords.

## 18.4 Operational status page

Atlas System Settings / Operational Status should include:

- Atlas API;
- database;
- Redis if retained;
- Atlas background worker/scheduler;
- Integration Runtime status;
- selected EE image/digest;
- `ansible-runner` / `ansible-core` versions;
- collection-lock status;
- currently running Integration jobs;
- queued/failed jobs summary;
- last successful run per Integration; and
- Connector implementation compatibility state.

Atlas must remain operational for read/manual functions if the Ansible runtime is down.

# 19. Connector, runtime implementation and protocol compatibility

## 19.1 Independent version axes

Track separately:

- Atlas application version;
- Atlas Integration Protocol version;
- Connector semantic version;
- Ansible Connector implementation version;
- Atlas Ansible Runtime version;
- Execution Environment image/digest;
- `ansible-core` version; and
- Collection lock/digest and individual Collection versions.

Example:

```text
Atlas                           0.1.0
Integration protocol            1.0
Proxmox Connector               1.0.0
Ansible implementation          1.0.0
Atlas Ansible Runtime           1.0.0
Execution Environment           atlas-infra-ee@sha256:...
ansible-core                    <pinned>
community.proxmox               2.0.0  (example current reference)
community.docker                5.3.0  (example current reference)
collection lock                 sha256:...
```

The example Collection versions reflect the ecosystem at the time of this design; the release lock is authoritative.

## 19.2 Connector/EE upgrades

An upgrade should:

1. build or select a new immutable EE with reviewed dependency versions;
2. validate its SBOM/licence inventory;
3. run Connector contract/fixture tests against the new EE;
4. perform live acceptance where required;
5. switch Integrations to the new implementation/EE only after successful validation; and
6. retain the prior EE image/digest for rollback for an appropriate period.

Do not silently upgrade Ansible Collections in a running Atlas release.

## 19.3 Protocol compatibility

AIP uses semantic major/minor compatibility:

- new optional fields: minor-compatible;
- changed meaning or required fields: new major.

The Atlas ingestion API must reject unsupported major versions with a clear Connector compatibility error.

## 19.4 Upstream collection change handling

Atlas should monitor dependency health at release/upgrade time, not continuously rewrite Atlas core for every upstream change. When a Collection changes:

- current pinned Atlas releases continue using the validated old version;
- CI tests the candidate version against fixtures/contracts;
- mapping changes are confined to the Connector implementation/normaliser;
- a broken Collection upgrade does not block the Atlas core release unless that Connector is explicitly part of the release acceptance set; and
- if a Collection is abandoned, replace it or isolate a direct client without changing AIP/domain code.

# 20. Backup and restore implications

Atlas backup and runtime reconstruction have separate concerns, but the runtime should be largely reproducible rather than stateful.

Atlas backup must preserve:

- IntegrationRuntime records and safe runtime metadata;
- Integration instances;
- Data Sources;
- Discovery Runs;
- Evidence, assertions and source links;
- Connector versions/configuration;
- encrypted secret records when using `AtlasEncryptedSecretProvider`; and
- secret key-version metadata.

The **master encryption key is intentionally outside the database**. Backup documentation must therefore define how the operator protects/restores that key. If the key is lost, encrypted Integration credentials are unrecoverable and must be re-entered; Atlas knowledge/history remains usable.

The Ansible runtime should be reconstructable from release artefacts:

- runtime service image/version;
- Execution Environment image/digest;
- collection/dependency lock;
- Connector playbooks/normalisers; and
- no required long-lived source credentials.

Atlas restore to a new installation should detect missing/incompatible runtime images and show:

> Integration Runtime requires revalidation / Execution Environment needs to be restored or pulled.

Losing runtime job artifacts must not lose accepted Atlas knowledge.

# 21. Testing strategy

## 21.1 API tests

Add tests for:

- IntegrationRuntime CRUD and permissions;
- Integration generic CRUD;
- scope/IDOR substitution;
- `SecretProvider` CRUD/replace/delete and non-disclosure;
- encrypted-secret master-key separation and failure behaviour;
- transient job secret leasing/redaction;
- catalogue manifest validation;
- Connector implementation install state;
- Test Connection orchestration;
- Run Now creation;
- callback token validation;
- wrong run/integration claims;
- expired token;
- duplicate batch replay;
- partial/full completion;
- no-longer-observed only after complete baseline;
- cross-customer payload attacks;
- Connector/runtime implementation version mismatch; and
- runtime unavailable behaviour;
- malicious/oversized Runner artifact rejection; and
- collection-lock mismatch behaviour.

## 21.2 Web tests

Cover:

- catalogue rendering;
- manifest-driven forms;
- secret fields not rehydrated;
- permission gating;
- runtime unavailable state;
- Run Now lifecycle;
- onboarding resume;
- Integration detail tabs;
- accessible status text;
- mobile layout; and
- dark/light/user accent themes.

## 21.3 Connector fixture and contract tests

Each Atlas Official Connector ships sanitized fixtures representing:

- minimum environment;
- normal homelab environment;
- empty environment;
- pagination;
- malformed source record;
- authentication error;
- permission-limited source;
- source timeout; and
- partial response.

## 21.4 Live acceptance lab

Before release, run against the actual homelab:

### Proxmox

- standalone/cluster visibility;
- all nodes;
- QEMU guests;
- LXCs;
- storage;
- bridges;
- repeat run is idempotent;
- stopped guest handling;
- node/guest removal appears only after complete snapshot.

### Docker/Compose

- all Docker hosts intended for Atlas;
- Compose projects;
- standalone container;
- multiple networks;
- named volumes;
- published ports;
- container recreation preserves meaningful identity strategy;
- stopped/one-off filtering.

### UniFi

- gateway;
- switches;
- APs;
- VLANs/Networks;
- management IP/MAC;
- device state;
- client correlation without flooding Assets;
- safe handling when uplink identity is absent.

# 22. Development roadmap

The integration subsystem should be developed in contained phases, each leaving the repository in a valid state.

## Phase I0 — Architecture, licensing boundary and contracts

**Outcome:** Repository agrees on the execution, credential and licensing boundaries before implementation starts.

Deliver:

- ADR: runtime-neutral AIP with `AnsibleRuntime` as the Community Preview reference runtime;
- ADR/security decision for `SecretProvider` and master-key separation;
- architecture rule that Atlas core does not import `ansible-core`;
- target Atlas-core licence/third-party component policy recorded without overstating final legal approval;
- AIP v1 JSON Schema;
- Connector Manifest v1 JSON Schema;
- `IntegrationRuntime` and `SecretProvider` Python protocols/interfaces;
- example Proxmox/Docker/UniFi fixtures;
- no user-facing feature yet.

Acceptance:

- schemas validate example payloads;
- AIP/domain contracts contain no Ansible-specific fields;
- no existing tests regress.

## Phase I1 — Ansible runtime and catalogue shell

**Outcome:** Atlas can health-check the isolated Ansible runtime and display a real Connector catalogue.

Deliver:

- `integration_runtimes` migration/model/API;
- `atlas-ansible-runtime` service/client wrapper;
- pinned initial Execution Environment build;
- runtime/EE health and compatibility reporting;
- official Connector catalogue loader;
- Configured/Catalogue/Runtime tabs;
- replace mock Integrations page with real empty/configured states;
- initial SBOM/licence manifest generation for the runtime image.

Do not implement live source discovery yet.

## Phase I2 — Generic Integrations, credential store and Test Connection

**Outcome:** Atlas can configure Proxmox, securely store its credentials and execute a bounded test through Ansible.

Deliver:

- additive generic Integration fields;
- 1:1 Data Source creation;
- `AtlasEncryptedSecretProvider` with master key outside DB;
- write-only credential API/UI lifecycle;
- manifest-generated connection forms;
- job secret leasing/redaction;
- Ansible Connector implementation state;
- Test Connection through a pinned EE;
- API/web/security tests.

Use Proxmox as the first vertical slice.

## Phase I3 — Discovery orchestration and AIP ingestion

**Outcome:** Run Now produces evidence/reconciliation through Ansible Runner.

Deliver:

- Atlas worker/scheduler dispatch path;
- run-scoped ingestion tokens;
- asynchronous Ansible job start/status/cancel;
- batch ingestion endpoint;
- batch idempotency;
- completion/failure endpoints;
- DiscoveryRun extensions;
- run details and Integration run status;
- evidence/assertion/reconciliation bridge;
- job workspace/secret cleanup guarantees.

## Phase I4 — Proxmox reference Connector

**Outcome:** Proxmox discovery uses the new Ansible/AIP path with collection-first source access.

Deliver:

- `community.proxmox` capability matrix and pinned version in the EE;
- Proxmox inventory/collection-based discovery wherever supported;
- reuse existing Atlas tests/semantic mappings;
- cluster, node, QEMU, LXC, storage/bridge coverage to the extent supported by validated source access;
- any temporary direct-API fallback explicitly isolated and documented;
- stable external IDs and complete-snapshot coverage;
- scheduled discovery;
- live Homelab acceptance.

## Phase I5 — Docker + Compose reference Connector

**Outcome:** Atlas discovers application/runtime structure through pinned `community.docker` content where practical.

Deliver:

- secure Docker connection mode(s), SSH/TLS as supported by the selected collection path;
- Docker Engine Asset;
- Compose projects;
- containers;
- Docker Networks → Atlas Networks;
- AssetInterfaces;
- named-volume/port facts;
- run-on/contains relationships;
- parent Proxmox Asset selection;
- noise controls;
- live Homelab acceptance.

## Phase I6 — UniFi Network reference Connector

**Outcome:** Atlas receives network-controller truth without coupling Atlas core to UniFi API changes.

Deliver:

- evaluate/vet current Ansible Galaxy collection options;
- use a suitable pinned collection if it meets read-only discovery/security/licensing requirements;
- otherwise use a small documented-API fallback isolated inside the runtime;
- site selection;
- gateway/switch/AP assets;
- Network/VLAN records;
- management interfaces;
- reliable documented uplinks only;
- known-client correlation;
- default suppression of unknown ephemeral clients;
- live Homelab acceptance.

## Phase I7 — Guided setup, schedules and operational polish

**Outcome:** A new community user succeeds without needing Ansible knowledge.

Deliver:

- onboarding profile selection;
- automatic/local runtime validation;
- Connector selection;
- initial-discovery review;
- Atlas-owned schedule presets;
- runtime/EE operational status;
- Connector/collection compatibility state;
- notifications for failed runs/credentials/runtime unavailable;
- concise Integration help text.

## Phase I8 — Community release hardening

**Outcome:** Integration system is suitable for Atlas Community Preview.

Deliver:

- fresh installation with the optional/separate Ansible runtime service;
- restart/reboot recovery;
- secret key backup/recovery guidance;
- Proxmox, Docker and UniFi permissions/configuration guides;
- exact Atlas/AIP/runtime/EE/collection compatibility matrix;
- immutable EE build/release process;
- SBOM and licence/notice bundle for Atlas and runtime image;
- GPL corresponding-source compliance process for redistributed runtime components where applicable;
- security review including secrets, SSRF, runtime isolation and callback token checks;
- end-to-end upgrade/rollback test;
- public README screenshots and 15-minute quick-start;
- feature ledger and release notes aligned to tested reality.

# 23. Codex implementation prompts

The following prompts are intended to be run sequentially. Before each phase, Codex should inspect `AGENTS.md`, relevant code/tests, current branch/status and the latest feature ledger. It must not assume this document proves implementation exists.

## Prompt I0 — architecture, licensing boundary and contracts

```text
Implement Phase I0 of the Atlas Integration Architecture specification v1.2.

Read AGENTS.md first. Inspect Integration, DataSource, DiscoveryRun, plugin SDK,
Proxmox plugin, worker, discovery/reconciliation services, product roadmap and
feature ledger before modifying anything.

Goal: establish contracts and boundaries only; do not build live discovery.

Deliver:
1. ADR selecting Ansible Runner + pinned Execution Environments as the first
   IntegrationRuntime implementation, with Atlas core forbidden from importing
   ansible-core or depending on Ansible internals.
2. ADR/design for SecretProvider. Default AtlasEncryptedSecretProvider must use a
   maintained authenticated-encryption library and a master key held outside the DB.
   Do not invent crypto.
3. Record the component/licensing boundary: Atlas core is separate from the Ansible
   runtime image; generate licence/SBOM metadata later. Do not claim legal approval.
4. Add AIP v1 JSON Schema.
5. Add Connector Manifest v1 JSON Schema with runtime-neutral semantics and an
   Ansible implementation descriptor/collection dependencies.
6. Add typed runtime-neutral IntegrationRuntime and SecretProvider protocols.
7. Add example manifests/fixtures for Proxmox, Docker and UniFi.
8. Add tests proving AIP/domain models contain no Ansible-specific fields.

Preserve existing APIs/migrations. No DB migration in this phase.
```

## Prompt I1 — Ansible runtime and catalogue

```text
Implement Phase I1.

Goal: Atlas can health-check an isolated Atlas Ansible Runtime and show a real
Connector catalogue. Do not implement source discovery yet.

Deliver:
1. IntegrationRuntime migration/model/API.
2. atlas-ansible-runtime client/service boundary with bounded internal API.
3. Initial immutable Execution Environment built reproducibly with ansible-builder
   or equivalent, using exact dependency pins.
4. Runtime health returns runtime, ansible-runner, ansible-core, EE digest and
   collection-lock metadata.
5. Official runtime-neutral Connector manifest loader.
6. Replace Integrations mock page with Configured / Catalogue / Runtime tabs using
   existing Atlas components/theme.
7. Runtime page shows Ansible runtime/EE health; no AWX/Ansible UI dependency.
8. CI emits initial SBOM/licence inventory for runtime image.
9. Permission, IDOR, error sanitation, rendering and compatibility tests.
```

## Prompt I2 — generic Integration instances and credentials

```text
Implement Phase I2.

Goal: configure a Proxmox Integration through Atlas, persist credentials safely in
Atlas, and Test Connection through Ansible without long-lived runtime secrets.

Deliver:
1. Generic Integration fields including connector/runtime/credential reference.
2. Real Integration CRUD with existing Customer/Site RBAC.
3. Exactly one DataSource per Integration.
4. AtlasEncryptedSecretProvider using a maintained AEAD library; master key comes
   from deployment secret/file/env and is never stored in PostgreSQL.
5. Write-only secret UI/API: Configured / Replace / Clear; never return plaintext.
6. Secret-bearing request/audit/error logging redaction tests.
7. Manifest-driven Add Integration wizard.
8. Job-scoped secret lease/materialisation into the isolated runtime and cleanup.
9. Proxmox Test Connection playbook through the pinned EE with sanitised result.
10. Migrations/API/web/security tests.

No Run Now yet.
```

## Prompt I3 — Run orchestration and AIP ingestion

```text
Implement Phase I3.

Goal: Run Now executes through Ansible Runner and submits AIP observations into
Atlas provenance/reconciliation.

Deliver:
1. Extend DiscoveryRun with runtime/connector/EE/collection/job fields.
2. Run-scoped signed ingestion tokens with dedicated signing key/audience.
3. Atlas worker/background orchestration for manual/scheduled job dispatch.
4. Async AnsibleRuntime job start/status/cancel.
5. AIP batch ingestion, completion and failure endpoints; tenant/source context
   comes from persisted Atlas records, never connector claims.
6. Idempotent batch retry.
7. Evidence/source identities/assertions/reconciliation using existing architecture.
8. Complete-snapshot absence logic only after successful complete runs.
9. Guaranteed secret lease/job-workspace cleanup on success/failure/cancel.
10. Comprehensive authorization/replay/partial/failure/regression tests.
```

## Prompt I4 — Proxmox reference Connector

```text
Implement Phase I4: Proxmox on the Ansible/AIP path.

First produce a capability matrix for the pinned community.proxmox Collection against
Atlas requirements. Prefer its inventory/plugins/modules for source interaction.
Reuse existing plugins/proxmox fixtures/tests and semantic mappings; do not create two
long-lived production Proxmox API clients.

Discover, where supported by the validated source-access path:
- standalone/cluster identity;
- nodes;
- QEMU VMs;
- LXCs;
- storage pools;
- bridges/network detail;
- cluster membership, runs_on, uses_storage and connected_to relationships;
- bounded source facts/status.

If an essential read-only field is not exposed by the collection, isolate any direct
API fallback inside this Connector implementation and document the maintenance reason.
Add stable IDs, complete-snapshot coverage, fixtures, schedule support and live acceptance.
```

## Prompt I5 — Docker/Compose reference Connector

```text
Implement Phase I5 using the pinned community.docker Collection where practical.

Prefer read-only info modules/plugins. Support secure remote access only; do not expose
an unauthenticated Docker TCP API. Keep Docker socket mode explicit/advanced.

Discover:
- Docker Engine;
- Compose projects using canonical labels;
- containers;
- Docker networks as Atlas Networks;
- interfaces/IP/MAC associations;
- named-volume and port-publishing bounded facts;
- container runs_on engine;
- project contains containers / project runs_on engine.

Allow optional parent Atlas Asset mapping to Proxmox VM/LXC/physical host. Exclude
noisy/transient objects and all environment-variable values/secrets. Add contract and
live acceptance tests.
```

## Prompt I6 — UniFi reference Connector

```text
Implement Phase I6.

Before coding source access, evaluate current Ansible Galaxy UniFi collections for:
maintenance, licence, documented-API use, read-only discovery coverage, permissions,
output stability and compatibility with the pinned EE. Record the decision.

Use a vetted pinned Collection if suitable. Otherwise use a small isolated Atlas-owned
read-only client or ansible.builtin.uri playbook against documented UniFi APIs only.
Never scrape controller databases.

Discover site, gateways/routers/firewalls, switches, APs, Networks/VLANs,
management interfaces/IP/MAC, bounded operational facts and reliable documented uplinks.
Use clients primarily to correlate known Assets; do not flood Assets by default.
```

## Prompt I7 — onboarding and operations polish

```text
Implement Phase I7.

Goal: a Homelab user can use integrations without knowing Ansible exists.

Deliver:
- resumable profile selection;
- automatic local Ansible runtime/EE validation;
- Connector selection;
- manifest-generated setup;
- first discovery progress + grouped Review Import;
- Accept all new while keeping duplicates/conflicts separate;
- Atlas-owned schedule presets;
- Integration health/last/next run summaries;
- Operational Status runtime/EE/collection section;
- notifications for runtime unavailable, credentials invalid, discovery failed and
  Connector/collection incompatibility;
- mobile/theme/accessibility validation.

Reuse Atlas design primitives; do not expose an Ansible/AWX admin UI in normal UX.
```

## Prompt I8 — release hardening

```text
Complete Phase I8 for Community Preview.

Do not add new source domains. Validate:
- fresh Atlas + optional/separate atlas-ansible-runtime installation;
- restart/reboot recovery;
- encrypted credential backup and external master-key recovery guidance;
- exact Atlas/AIP/runtime/EE/ansible-core/Collection compatibility matrix;
- immutable EE build and rollback;
- SBOM plus third-party licence/notices and corresponding-source process for
  redistributed GPL runtime components;
- source permission guides;
- security review for secret handling, SSRF, process/container isolation, untrusted
  Collection prevention and callback tokens;
- end-to-end upgrade from previous release candidate;
- production build/full automated test suites;
- public README screenshots/15-minute quick-start;
- feature ledger and release notes aligned to tested reality.

Report remaining limitations explicitly rather than delaying release for enterprise features.
```

# 24. Community Preview acceptance criteria

Atlas should not call the integration subsystem release-ready until the following are true.

## Runtime

- Atlas can use the isolated Ansible runtime without requiring AWX or another UI.
- Runtime outage does not take Atlas read/manual functionality down.
- Atlas core/domain code imports no `ansible-core` package.
- Runtime health exposes EE/Runner/Core/collection compatibility safely.
- Current EE/dependencies are pinned and reproducible.

## Credentials

- Source credentials are stored only through `SecretProvider`.
- Plaintext secrets are never returned after save.
- Atlas DB does not contain the master encryption key.
- Job-scoped secret material is cleaned up after run completion/failure/cancel.
- Secret values do not appear in logs, audit metadata, AIP or retained runtime artifacts.

## Catalogue and configuration

- Proxmox, Docker and UniFi appear from runtime-neutral Connector manifests.
- Forms are generated from manifests.
- Collection/source-access strategy and exact validated versions are visible to administrators.
- Test Connection is reliable and sanitised.
- An Integration can be disabled without losing knowledge.

## Discovery

- Run Now works end-to-end through Ansible Runner.
- Atlas-owned scheduled runs work.
- Runs appear in existing Discovery history.
- Complete/partial state is truthful.
- Batch retry is idempotent.
- No source can submit data into another Customer/Site.

## Knowledge integrity

- Evidence is retained.
- Source links are stable.
- New entities can be accepted efficiently.
- Conflicts create reconciliation rather than silent overwrite.
- Missing entities are considered only after successful complete snapshots.
- Graphs use accepted Atlas records, not arbitrary raw runtime payloads.

## Reference Connectors

- Proxmox discovers the intended cluster/compute scope and documents any collection gaps.
- Docker discovers application/runtime scope and Compose grouping.
- UniFi discovers agreed network scope using a vetted collection or isolated documented-API fallback.
- Repeated unchanged runs do not produce noisy duplicate changes.

## Security/licensing/release

- Runtime image has an SBOM and third-party licence/notice inventory.
- GPL components are confined to the runtime distribution boundary and required source-compliance process is documented.
- Atlas core remains separately buildable/runnable without the Ansible runtime.
- No unreviewed/unpinned Galaxy Collection is automatically installed.

## UX

- Homelab onboarding is resumable.
- A normal user need not know or operate Ansible directly.
- Errors identify whether the problem is Atlas, runtime/EE, credentials, Collection or source.
- UI works in light/dark/user accent modes and on a practical mobile layout.

# 25. Recommended follow-on roadmap after Community Preview

Once the core Connector model is released and proven, prioritise integrations that add new kinds of operational knowledge rather than simply increasing Connector count.

For every candidate, first evaluate the Ansible ecosystem and prefer a maintained Collection over a new Atlas vendor client.

Recommended sequence:

1. **Nginx Proxy Manager / Traefik** — proxy route relationships and application endpoints.
2. **Cloudflare** — public DNS/tunnel/exposure context.
3. **Uptime Kuma** — monitoring coverage and current endpoint state.
4. **Synology / TrueNAS / backup sources** — storage and recovery coverage.
5. **Authentik** — authentication protection relationships.
6. **Tailscale** — remote access/network overlay context.
7. **Home Assistant** — optional Homelab capability mapping.

Where no mature Collection exists, encourage community-owned Connectors or direct AIP collectors before adding a new Atlas-maintained API client.

A second execution runtime (for example n8n or a purpose-built remote collector) should only be prioritised when it unlocks a materially different maintained integration ecosystem or MSP execution model. Runtime plurality is supported by AIP, but it is no longer a Community Preview deliverable.

# 26. Open implementation decisions

These decisions can be made during the relevant phase without reopening the main architecture:

1. Exact maintained AEAD library/algorithm and master-key provisioning/rotation mechanism for `AtlasEncryptedSecretProvider`.
2. Whether the local `atlas-ansible-runtime` is in the default Compose profile or an optional profile pulled as a separate image.
3. Internal API transport between Atlas worker/API and local runtime (internal HTTP/Unix socket), while retaining a future remote mode.
4. Exact initial `ansible-core` / Runner / base-image pins and EE rebuild cadence.
5. Proxmox capability gaps that require a temporary direct-API fallback versus Collection-only implementation.
6. Which UniFi Galaxy Collection, if any, is mature enough for default inclusion.
7. Whether Docker SSH or TLS API ships first; local socket remains advanced.
8. Whether the existing Atlas worker is sufficient for schedules/job orchestration or needs a small dedicated integration queue.
9. Formal Atlas core licence selection (Apache-2.0 is the current target posture) and whether to adopt DCO/CLA before accepting substantial external contributions.
10. Exact commercial-distribution legal review/checklist for the Ansible runtime image and bundled Collection licences.

None of these should reopen the fundamental boundaries established by this specification.

# 27. Final implementation principles

The implementation should be judged against the following rules:

- **Atlas is the product; Ansible is replaceable execution infrastructure.**
- **Atlas core never imports or depends on Ansible internals.**
- **AIP and Connector semantics belong to Atlas.**
- **Use maintained Ansible Collections for vendor API interaction wherever practical.**
- **Atlas owns credential lifecycle through a `SecretProvider`; Ansible receives job-scoped secrets only.**
- **The runtime can fail without taking Atlas knowledge/manual functions down.**
- **Customer/Site scope comes from Atlas, never Connector claims.**
- **Discovery creates evidence before it changes accepted knowledge.**
- **Complete snapshots are explicit.**
- **Collection/EE versions are pinned; upgrades are deliberate and tested.**
- **The first three reference Connectors prove the semantic and execution pattern, not special cases.**
- **The catalogue UI hides execution complexity without hiding operational truth.**
- **Homelab onboarding is simple, while the data model remains compatible with Organisation/MSP growth.**
- **Atlas core and the Ansible runtime have an explicit security and licensing boundary.**
- **Do not build enterprise automation features to justify the release. Make discovery excellent, release Atlas, and learn from real users.**

A new source should be able to integrate by combining maintained ecosystem source access with Atlas Connector semantics, or by emitting AIP directly, without changes to Atlas domain code.

# Appendix A — Source references

The design uses current public product capabilities documented by the relevant projects as of 28 September 2026.

- Ansible Runner — stable interface for external tooling to invoke Ansible and consume structured job events/artifacts; process/container isolation and Execution Environment support (`ansible.readthedocs.io/projects/runner`).
- `ansible-core` — upstream Ansible engine; GPL-3.0-or-later (`github.com/ansible/ansible`).
- Ansible Runner — Apache-2.0 (`github.com/ansible/ansible-runner`).
- Ansible Builder — reproducible Execution Environment builder; Apache-2.0 (`github.com/ansible/ansible-builder`).
- Ansible Galaxy — community/vendor Collections (`galaxy.ansible.com`).
- `community.proxmox` — Proxmox inventory/modules; current documentation shows Collection 2.0.0 and `ansible-core` 2.17+ support at the time of this design; GPL-3.0-or-later (`docs.ansible.com`, `github.com/ansible-collections/community.proxmox`).
- `community.docker` — Docker modules/plugins; current documentation shows Collection 5.3.0 at the time of this design; primarily GPL-3.0-or-later with some Apache-2.0 vendored content (`docs.ansible.com`, `github.com/ansible-collections/community.docker`).
- Docker — remote daemon/API security and Compose metadata (`docs.docker.com`).
- UniFi — documented Network API (`developer.ui.com`); third-party Galaxy content must be vetted before default inclusion.
- Proxmox — cluster/nodes/guests/storage/networking (`pve.proxmox.com`).
- Optional future external secret provider: OpenBao, MPL-2.0 (`openbao.org` / `github.com/openbao`).

Licence descriptions in this architecture are engineering constraints, not legal advice. Verify the exact versions and distribution artefacts before commercial release.

# Appendix B — Proposed repository changes by phase

| Phase | Main paths |
|---|---|
| I0 | `docs/decisions`, `docs/product`, `integrations/protocol`, runtime-neutral contracts, security/licensing ADRs |
| I1 | `apps/api/app/models.py`, runtime routes/services, `apps/runtime/ansible` or dedicated runtime service, `execution_environments/*`, Integrations UI |
| I2 | Integration migration/routes, `SecretProvider`, encrypted-secret migration/service, manifest forms, Proxmox Test Connection |
| I3 | ingestion routes/services, DiscoveryRun migration, token service, worker scheduler/queue, Ansible job orchestration, run UI |
| I4 | `integrations/connectors/proxmox/implementations/ansible`, migrate/reuse Proxmox fixtures/tests |
| I5 | `integrations/connectors/docker/implementations/ansible`, Networks/Interfaces ingestion extensions |
| I6 | `integrations/connectors/unifi/implementations/ansible`, collection evaluation/fallback and client-correlation tests |
| I7 | guided setup, Operational Status, notifications, scheduling UX |
| I8 | docs, EE build/release CI, SBOM/licence artefacts, security/live acceptance documentation |

# Appendix C — Suggested permissions

Preserve current `integrations.view` and `integrations.manage` and add narrowly only where needed.

Suggested keys:

- `integrations.view` — view configured integrations, catalogue and safe status.
- `integrations.manage` — create/edit/disable/remove Integration instances.
- `integrations.run` — Test Connection and Run Now within assigned scope.
- `integration_runtime.view` — inspect runtime health/version; normally administrator only.
- `integration_runtime.manage` — configure runtime and install/upgrade Connector implementations; global administrator only.
- existing `discovery_runs.archive/delete` remain separate lifecycle permissions.

Do not use a broad integration permission to bypass existing Customer/Site authorization.

# Appendix D — Licensing and distribution boundary

This appendix records the intended engineering boundary so that Community and future commercial distributions can be reviewed consistently.

| Component | Intended boundary | Licence posture / action |
|---|---|---|
| Atlas API/Web/knowledge plane | Atlas core repository/images | Target permissive licence such as Apache-2.0; formal repository decision required. |
| AIP schemas / Connector SDK | Atlas core | Keep permissive to encourage community Connector development. |
| Atlas Ansible Runtime service code | Separate runtime component/image | Keep separate from domain code; choose a licence compatible with its dependencies and distribution model. |
| Ansible Runner | Runtime dependency | Apache-2.0 upstream; preserve notices. |
| Ansible Builder | Build-time dependency | Apache-2.0 upstream; preserve notices when redistributed as applicable. |
| `ansible-core` | Runtime/EE dependency | GPL-3.0-or-later upstream; preserve licence/source obligations for distributed copies/modifications. |
| Ansible Collections | Runtime/EE dependencies | Record exact licence per version. Do not assume all Collections share one licence. |
| Connector normalisers that only consume JSON | Runtime-neutral/Atlas-owned code | Keep independent of Ansible internals where possible. |
| Custom Ansible plugins importing/extending Ansible APIs | Runtime side only | Treat as GPL-bound/compatible code unless legal review establishes otherwise. |

Release engineering requirements:

- maintain a machine-readable SBOM for Atlas images and the runtime/EE separately;
- preserve upstream licence/notices;
- retain source/patches for redistributed GPL components as required;
- pin exact dependency versions used in each release;
- avoid copying GPL implementation code into Atlas core;
- ensure the Atlas core remains buildable and functional for manual/read use without the Ansible runtime; and
- obtain a software-licensing review before the first paid/commercial distribution.

For community contributions, adopt DCO or CLA policy before contribution volume makes later relicensing materially difficult.
