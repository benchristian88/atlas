# I0 completion and validation record

Date: 11 October 2026. **Result: PASS WITH DOCUMENTED FOLLOW-UPS.**
I0 architecture/contracts scope is complete; no runtime/vendor product completion
is claimed. Database/nginx-dependent validation remains unexecuted locally.

## Repository baseline

Inspected branch `feature/integration-rel-0`, HEAD
`90e04a76982c314fff2191e84ca6bd1a8cabcb07`. Initial `git status --short`:

```text
?? docs/architecture/integrations/
?? docs/history/integrations/
```

These contained the supplied v1.3 design, historical v1.2 and five mockups.
Baseline copies were retained in temporary storage before edits. All five PNG
hashes are unchanged. No reset/stash/rebase/commit/merge/tag/release/push or remote
repository creation occurred. All changes are left uncommitted.

## Alignment result and material discrepancies

[33-row matrix](integration-alignment-matrix.md): **10 REUSE EXISTING,
13 EXTEND EXISTING, 10 GENUINELY NEW**. Reuse coverage-aware lifecycle,
run-observed membership, evidence, assertions/acceptance, reconciliation,
Changes/audit, managed taxonomy, tenancy and plugin technical semantics.
Extend generic Integration/DataSource/run metadata, source links, facts,
Networks/Interfaces/coverage, RBAC, worker, encryption/backup, packaging and
existing web surfaces. New responsibilities are mappings, control/run credentials,
runtime protocol/execution, catalogue/package state/provenance, AIP adapter,
onboarding and batch receipt/finalisation ledger.

Key evidence: `apps/api/app/services/discovery_observations.py` owns baseline/
absence/re-observation, demonstrated by `test_complete_snapshot_detects_missing_once_without_mutating_asset`,
`test_partial_snapshot_never_creates_missing_items`,
`test_failed_complete_run_cannot_process_absence`, `test_reobserved_entity_resolves_missing_episode`.
`entity_resolution.py`, `knowledge_assertions.py` and `reconciliation.py` own
source links, source-current/accepted state and operator decisions.
`encrypted_data.py` registers only the MFA adapter today; Integration secrets
must extend its existing all-adapter rewrap transaction.

Material conflict flagged: legacy `AtlasDiscoverySync._sync` directly updates
records, creates unknown taxonomy and marks omissions stale without complete
coverage. Code/regressions remain unchanged. New AIP must extend the safer
existing evidence/reconciliation owners, not reuse that direct-sync behavior.
Current worker is a placeholder, Integration UI is an unavailable-state scaffold,
source links/absence are Asset-only, and each run has one aggregate coverage key.
Conservative aggregate partial status preserves safer current eligibility;
independent-domain absence requires explicit additive implementation first.
Existing SDK/plugin code is AGPL; ownership review must precede extracting/reusing
implementation into an Apache project. No silent relicensing was performed.

## Files and architecture baseline

- [Active v1.3](Atlas_Integration_Architecture_and_Design_Specification_v1.3.md):
  repository-grounded ownership, staging/extraction, explicit callback sealing,
  safe runtime/store and coverage authority; retained useful source/security/UI detail.
- [Historical v1.2](../../history/integrations/atlas-integration-architecture-v1.2.md):
  explicit superseded status, preserved historical policy, repaired links to the
  five existing mockups and labels for missing original diagram artifacts.
- [Matrix](integration-alignment-matrix.md), [roadmap](integration-roadmap.md)
  and this record: evidence, I0–I8 phase boundary, I4 register and validation.
- Documentation/ADR/history indexes, `architecture-v0.md`, product status and
  feature ledger: discoverability and truthful target/current/legacy boundaries.
- Contracts listed below: static artifacts/tests only. Five pre-existing PNGs
  remain byte-identical and untracked, not newly generated or edited.

There is **one active Integration design**. Historical v1.2 is not competing policy.
No migration or production schema change; existing Alembic head remains
`20261004_0026`. Existing API routes/contracts, UI, runtime processes and production
permission keys are unchanged. Authorization/customer/site enforcement is preserved;
new contracts disallow Connector-selected tenancy and require existing scope owners.

## Accepted ADRs

[ADR index](../../decisions/README.md) adds:

- 0003: runtime-neutral AIP/Ansible boundary and Docker/systemd parity.
- 0004: existing data-key SecretProvider/rewrap, separate control and run credentials.
- 0005: three-project licensing/ownership and verbatim SDK extraction.
- 0006: official immutable provenance-verified catalogue and protected execution.
- 0007: global one-active-version package/scoped Integration lifecycle.
- 0008: exact global taxonomy mapping and namespaced-fact model.
- 0009: read-only technical official v1 discovery.

Existing accepted ADRs 0001/0002 are unchanged; no historical decision was rewritten.

## Contracts

[Contract README](contracts/README.md) defines staging/sole SDK ownership,
[Draft 2020-12](https://json-schema.org/draft/2020-12) validation, replay/finalisation,
coverage mapping, bounds, source identity, secret exclusion and detached distribution
metadata (no self-referential bundle hash). Artifacts:

- `aip-v1.schema.json`, `connector-manifest-v1.schema.json`.
- `integration-runtime.md`, `secret-provider.md` interface specifications.
- Three non-installable Manifest examples: Proxmox, Docker, UniFi.
- Ten AIP messages: multi-batch Proxmox complete, partial and failed completion;
  Docker/UniFi complete observations and completion.
- `identity-examples.json`, `requirements-i0.txt`, `tests/test_contracts.py`.

Examples contain no credentials, executable bundles or source qualification
claims. Their digests/URLs/dependency locks are illustrative. Runtime-specific
packaging metadata is isolated from runtime-neutral domain fields. Before I1 move
new schemas verbatim into the separate sole canonical SDK; no production imports
or duplicate SDK package were introduced.

## Validation executed

Existing development interpreter is Python **3.14.7**, rather than CI's Python
3.12. Missing `cryptography`, `pyotp`, `redis` and test-only JSON Schema/format
extras were installed only under `/private/tmp/atlas-i0-test-deps` from their
existing pinned requirements/test dependency. The initial focused command stopped
at missing imports; it was rerun successfully after provisioning. Static contract
checks caught and corrected receipt-order determinism and missing optional format
validators. Successful final commands follow (working directories are explicit).

Repository root:

```bash
PYTHONPATH=/private/tmp/atlas-i0-test-deps apps/api/.venv/bin/python -m pytest docs/architecture/integrations/contracts/tests -q --tb=short
```

**77 passed.** Schema/metaschema, all Manifest/AIP examples, stream bindings/
references/replay, complete/partial/failed eligibility, declared classes and typed
facts, executable-content/tenant/credential rejection, formats, deterministic
identity/container recreation and infrastructure-only UniFi. Static validation
does not pretend production runtime/ingestion exists.

`apps/api`:

```bash
PYTHONPATH=/private/tmp/atlas-i0-test-deps:. ../../apps/api/.venv/bin/python -m pytest tests/test_knowledge_foundation.py tests/test_discovery_sync.py tests/test_knowledge_lifecycle.py tests/test_administration.py tests/test_mfa.py tests/test_backups.py tests/test_updates.py tests/test_release_distribution.py ../../plugins/sdk/tests ../../plugins/proxmox/tests -q --tb=short
PYTHONPATH=/private/tmp/atlas-i0-test-deps:. ../../apps/api/.venv/bin/python -m pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests -q -rs --tb=short
PYTHONPATH=/private/tmp/atlas-i0-test-deps:. .venv/bin/python -m pytest tests/test_repository_docs.py -q --tb=short
PYTHONPATH=/private/tmp/atlas-i0-test-deps:. .venv/bin/python -m alembic heads
```

Focused baseline: **266 passed**. Full existing regression: **674 passed,
211 skipped**, zero failures. Repository Markdown/link/licence checks: **14
passed**, including final report. Alembic: **one head, 20261004_0026**.
The skipped tests require configured disposable PostgreSQL test databases or
nginx >=1.28; they were not executed. Their database/Redis-backed restore and
nginx behavior is not locally requalified. Existing deprecation warnings remain.

`apps/web`:

```bash
npm test
```

**280 passed**, zero failures/skips. Production frontend build was not run because
I0 changes no frontend source/build/runtime behavior. No live source, container,
native install or package-release acceptance was performed by I0.

Repository root:

```bash
git diff --check
```

Clean. Existing repository documentation tests also inspect untracked Markdown.
Additional inspection checked all new local Markdown/image targets, removed
broken `/mnt/data` export paths and confirmed all five mockup hashes unchanged.
No validation evidence is inferred from the architecture's accepted status.

## Contradictions removed from active Integration policy

Confirmed: Ansible-first/runtime-neutral (no Windmill runtime); AGPL Atlas core;
existing application encryption key (no independent Integration master key);
local infrastructure-only UniFi (no client discovery); Atlas-owned scheduling;
verified installed entry points only; logical Docker workloads (container ID
only observation); no automatic Service/Business Function creation; global
version mappings; no dynamic runtime dependency mutation. References to excluded
choices in explanatory prose/history do not prescribe them. Review-first default
and explicitly enabled optional auto_accept_new target remain distinct from
source fact classification and I0 implementation status.

## I1 hand-off and open research

I1 only: SDK extraction/released consumption; default private runtime health/
capabilities/auth; protected verified store and global catalogue/installed-state
shell; existing Docker/systemd installer/package parity; generic catalogue UI
states following retained mockups. Credential persistence/Test Connection is I2;
worker/scheduling/callback ingestion is I3; live vendors are I4–I6. I0 implemented
no DB migration, runtime/service/container, UI, credential persistence, live
catalogue install, scheduling or vendor discovery.

Open implementation evidence: I1 verifier/offline provenance/store layout and
exact runtime/Collection lock + SDK ownership/publishing; I3 canonical scope
encoding and dispatch/finalisation/recovery bounds; I4 dated official/community
review and actual API-call/least-privilege ACL matrix/field regressions; I5 stable
ordinal/standalone rename/recreate identity and SSH/Collection path; I6 documented
local API-key cloud dependency/fallback auth; I8 dependency/SBOM and package/platform
acceptance. The full I4 source URLs/seeded edge-case register are in the roadmap;
review date remains pending I4, with no fabricated upstream findings.

## Exact repository state

`git status --short --untracked-files=all` (all files left uncommitted):

```text
 M docs/README.md
 M docs/architecture/architecture-v0.md
 M docs/decisions/README.md
 M docs/history/README.md
 M docs/product/feature-ledger.md
 M docs/product/status.md
?? docs/architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md
?? docs/architecture/integrations/assets/add-proxmox-wizard.png
?? docs/architecture/integrations/assets/connector-catalogue.png
?? docs/architecture/integrations/assets/integration-detail.png
?? docs/architecture/integrations/assets/integrations-overview.png
?? docs/architecture/integrations/assets/runtime-settings.png
?? docs/architecture/integrations/contracts/README.md
?? docs/architecture/integrations/contracts/aip-v1.schema.json
?? docs/architecture/integrations/contracts/connector-manifest-v1.schema.json
?? docs/architecture/integrations/contracts/fixtures/docker-complete-1.json
?? docs/architecture/integrations/contracts/fixtures/docker-complete-completion.json
?? docs/architecture/integrations/contracts/fixtures/proxmox-complete-1.json
?? docs/architecture/integrations/contracts/fixtures/proxmox-complete-2.json
?? docs/architecture/integrations/contracts/fixtures/proxmox-complete-completion.json
?? docs/architecture/integrations/contracts/fixtures/proxmox-failed-completion.json
?? docs/architecture/integrations/contracts/fixtures/proxmox-partial-1.json
?? docs/architecture/integrations/contracts/fixtures/proxmox-partial-completion.json
?? docs/architecture/integrations/contracts/fixtures/unifi-complete-1.json
?? docs/architecture/integrations/contracts/fixtures/unifi-complete-completion.json
?? docs/architecture/integrations/contracts/identity-examples.json
?? docs/architecture/integrations/contracts/integration-runtime.md
?? docs/architecture/integrations/contracts/manifests/docker.json
?? docs/architecture/integrations/contracts/manifests/proxmox.json
?? docs/architecture/integrations/contracts/manifests/unifi-network.json
?? docs/architecture/integrations/contracts/requirements-i0.txt
?? docs/architecture/integrations/contracts/secret-provider.md
?? docs/architecture/integrations/contracts/tests/test_contracts.py
?? docs/architecture/integrations/i0-completion-report.md
?? docs/architecture/integrations/integration-alignment-matrix.md
?? docs/architecture/integrations/integration-roadmap.md
?? docs/decisions/0003-runtime-neutral-integrations.md
?? docs/decisions/0004-integration-secret-lifecycle.md
?? docs/decisions/0005-connector-project-ownership.md
?? docs/decisions/0006-verified-connector-supply-chain.md
?? docs/decisions/0007-global-connector-scoped-integration.md
?? docs/decisions/0008-connector-taxonomy-and-facts.md
?? docs/decisions/0009-read-only-official-connectors.md
?? docs/history/integrations/atlas-integration-architecture-v1.2.md
```
