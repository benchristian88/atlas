# I4B — Proxmox discovery candidate implementation

Review date: **12 October 2026**. The separate **0.2.0-i4b.1** Connector candidate
implements secured collection discovery and deterministic real-runtime acceptance.
**Proxmox 9.2.11 remains UNQUALIFIED; I4 is incomplete.** Atlas's shipped production
bootstrap remains **Proxmox 0.1.0 probe-only**. Native Debian/systemd LIVE acceptance
remains outstanding. No commit, push, merge, Connector release, production
activation or source qualification was performed.

## Implementation ownership and compatibility

Approximately **92% of added executable implementation is in atlas-connectors**
and **8% in Atlas**, excluding tests, metadata and documentation. Every
Proxmox-specific source call, transport adaptation, identity, normalization,
relationship/fact rule and completeness/ACL decision lives in atlas-connectors.
Atlas has no new vendor client/import, source normalization, storage/VMID/node
semantics or source-specific API schema. The legacy Proxmox plugin is unchanged.

The candidate declares SDK **1.1.0**, AIP **1.0**, exact community.proxmox **2.0.0**
with reviewed archive SHA-256
`77e02e0d1e341c6b064900fe58484ad8880cee4832f5fd65d09834ed068216f6`, and runtime
baseline >=**1.2.0**, <2.0.0. Acceptance uses the unchanged
`atlas-ansible-i4a-v1` / **1.2.0**, runtime **0.3.1**, ansible-core **2.19.7**,
ansible-runner **2.4.3** and proxmoxer **2.3.0**. See the
[I4A baseline](i4a-runtime-baseline.md). The SDK repository and pinned wheel/schema
contracts are unchanged. No migrations are required; Alembic remains at its
existing single head `20261012_0029`.

## Source access, transport and contained collection gaps

`discover.yml` invokes the fixed `library/atlas_discover.py` module and writes only
canonical AIP NDJSON to the private runtime-provided output. It receives no Atlas
ingestion/control token and performs no callbacks or source writes.

The candidate reuses the reviewed collection's `ProxmoxAnsible` connection setup,
Proxmoxer token auth, resource routing and JSON serializer, plus the cluster,
VM/current-config, storage-list and node-network info implementations. A secured
Requests session/adapter replaces the session before its first authenticated read.
The actual socket is pinned to one vetted DNS peer, with original-host SNI and
certificate checking or SHA-256 fingerprint verification **before headers**.
Environment proxies/netrc, redirects, writes, discovered-address requests,
unreviewed paths/parameters, compressed responses and insecure discovery are
rejected. Source bodies/calls/results and connect/read/whole-run time are bounded.
Raw flags are checked before upstream's potentially lossy boolean conversions.
Upstream exception bodies/tracebacks and known credential echoes are discarded.

Contained exceptions, all on that same secured session:

- `/nodes` separates node inventory from node-info's coupled network/version reads.
- Each node's QEMU/LXC list executes even when upstream resource seeding is empty;
  lists/seeds/config presence are compared before COMPLETE.
- `/nodes/{node}/storage` supplies operational storage status unavailable through
  a contained info module. Optional capacity/availability is local active pools
  only; shared per-node totals, named configuration and contents are omitted.
- Own targeted/effective permissions and `/access/acl` supply completeness proof
  absent from collection modules. An unfiltered ACL read requires `Sys.Audit` on
  `/access`, since effective-permission dumps omit zero-permission paths.

No independent long-lived source client, Allocate privilege, guest-agent read or
automatic failover is added. Full call/ACL/security documentation is in the
[Connector discovery specification](https://github.com/benchristian88/atlas-connectors/blob/feature/i4b-proxmox-discovery/connectors/proxmox/docs/discovery.md).
That URL identifies candidate branch content and does not imply publication or
production qualification.

## Identity, AIP and coverage decisions

Identities are scoped to the retained Atlas DataSource, never endpoint/display
labels/MACs alone. Guests use type+VMID independent of placement/rename. Nodes
use source node names because no durable physical UUID is proven by these reads;
rename is an explicit limitation. Actual clusters use one source-local deployment
identity; standalone has no fake cluster. Shared storage requires explicit source
shared evidence; local storage includes node+storage ID. Bridges/subnets remain
node-local. Interfaces use owner+slot/name; duplicate MACs remain distinct.
Relationships hash ordered semantic class/source/target inputs. Replacing a
source behind an unchanged endpoint and VMID reuse remain identity limitations.

AIP Assets are cluster/node/QEMU/LXC/storage/bridge. Recommended managed mappings
include hypervisor_node, virtual_machine, container, storage_pool, cluster and
network_device; unresolved/incompatible required taxonomy needs an operator
choice. Networks/Interfaces use canonical CIDR/ownership/membership/MAC/static-IP
fields. Only explicit current bridge subnets produce source-local Networks.
Tagged/trunk attachments do not infer unsupported logical membership.
Guest membership also requires an explicit static subnet matching the bridge
CIDR; unknown guest IPs and different subnets do not assert that binding.

Observed relationships: node→cluster `proxmox.member_of`, guest→node
`proxmox.runs_on`, guest→storage `proxmox.uses_storage`, node/guest→bridge
`proxmox.connected_to`. Facts are fixed bounded scalars: VMID, template,
deployment mode, power/online state, storage type/shared state, local capacity/
availability, bridge VLAN awareness and interface VLAN tag. Version uses the AIP
envelope. Source availability/power is never Atlas lifecycle or operational impact.
Descriptions, comments, arbitrary configuration, environment values, commands,
mount contents and secrets are excluded.

COMPLETE requires the dispatched required scope/classes/domains to execute,
all mandatory calls/configs to succeed, coherent membership/placement/lists/storage,
no offline node/staging/malformed discard/limit breach/unresolved topology,
propagated whole-scope token/backing-user privileges, explicit effective checks on
all relevant ACL paths including hidden overrides, and unchanged inventory/ACL
proof before/after collection. Enumeration order and volatile counters do not
alter membership signatures. Uncertainty/enrichment failure yields PARTIAL;
initial mandatory failure/top-level limits yield a failed seal. Empty lists alone
never prove coverage. The dispatched I3 aggregate key is echoed unchanged.
Only existing successful COMPLETE I3 finalisation can consider Asset absence.
No Connector absence/deletion/acceptance logic or reconciliation redesign exists.

## Atlas generic blockers and changes

1. **Retained-source repoint protection was missing.** Integration PATCH could
   change a URL while retaining successful discovery history/DataSource identity.
   The generic service now fixes all non-secret URL fields after any completed
   source-backed run, including PARTIAL. HTTP 409 `source_identity_locked` directs
   creation of a new Integration. Before history, existing edits remain allowed.
   Display/scopes/TLS trust/credential rotation remain editable.
2. **Probe adapters stripped bounded capability diagnostics.** Runtime and API
   now independently validate at most 16 identifier-only diagnostics with generic
   state/path-category enums and optional privilege. Unknown/free-text/path/blob
   fields and credential echoes are rejected. Private probe output is bounded to
   8 KiB. AIP/SDK contracts and existing API routes remain unchanged; the optional
   probe response field is additive.
3. **Acceptance plumbing is test-only.** `i4b-fixture` derives candidate code with
   an injected deterministic source socket. Its synthetic `fixture-only`
   qualification does not qualify Proxmox. Normal installation still rejects the
   actual unqualified candidate. Tests use temporary stores/transactions; release
   packaging excludes tests. Production catalogue/bootstrap files are unchanged.

No database/schema, frontend/UI/navigation, managed permission or existing route
changes are needed. The probe diagnostic field is additive; endpoint locking is
the requested deliberate restriction. Existing backend scoped manage/run RBAC,
Customer/Site ownership, Integration locks, encrypted credentials, exact verified
package identity, run-scoped callbacks and reconciliation remain authoritative.
Regression tests cover cross-tenant/RBAC rejection before revealing history.

## Validation

The final candidate and regenerated test-only bundle passed the checks below.
The fixture chain is candidate code → fixed playbook → actual Runner → aip.ndjson
→ SDK validation → authenticated I3 batches → PostgreSQL evidence/reconciliation
→ COMPLETE/PARTIAL finalisation. COMPLETE observations require explicit review;
PARTIAL after an accepted COMPLETE baseline preserves Assets with no absence.
Tests also cover source failure, cancellation/process-tree cleanup, replay,
malformed AIP, limits and existing restart/recovery behavior.

Python 3.12 validation uses the existing I4A Docker image with network disabled
and read-only sources. Test tools are mounted separately; its dependency baseline
is not mutated. The image intentionally has no Git: exported-source tests receive
an explicit test-only HEAD context. Reproducible builds also run in the real Git
checkout. Local real-runtime PostgreSQL acceptance uses the installed pinned
native-style Python environment, not a live systemd deployment.

## Material files and remaining gates

The final file inventory and repository state follow below. All Proxmox-specific
files belong to atlas-connectors. Atlas changes are the two generic policies,
their regression/runtime fixture tests, release-critical selector and truthful
contract/roadmap/feature-ledger documentation. SDK files are untouched.

Remaining live gates: exact Proxmox 9.2.11 API/ACL compatibility; dedicated
privilege-separated token/backing-user/no-access cases; verified/fingerprint TLS,
changed certificates/DNS/redirects; offline endpoint/nodes; migration, recreation,
node rename/join/leave; shared/local/restricted storage; staging and VLAN/trunks;
limits, cancellation and repeated COMPLETE/PARTIAL snapshots. Optional guest-agent
IPs, physical disks, automatic failover and cross-source merging remain excluded.
Native Debian/systemd LIVE acceptance is still outstanding. No fixture acceptance
substitutes for those source/deployment gates.

### Executed commands and results

Database-backed commands loaded the existing private disposable PostgreSQL
validation environment; credential values were never included in documentation.
The disposable Redis URL was `redis://127.0.0.1:16379/0`. Runtime Python was
`/private/tmp/atlas-i4a-runtime-venv/bin/python`.

| Validation | Command / environment | Actual result |
| --- | --- | --- |
| Full atlas-connectors suite | `ATLAS_TEST_RUN_ANSIBLE=1`, exact reviewed `ATLAS_TEST_COLLECTIONS_PATH`, runtime Python with separate pytest support; `python -m pytest -q --tb=short` | **98 passed**, native-style Python 3.14.7; four actual fixed-playbook Runner cases included. |
| Pinned Python 3.12 image | `docker run --rm --network none` using existing `atlas-runtime:i4a-validation`, read-only Connector/test-tool mounts, protected `/app/collections`, `ATLAS_TEST_RUN_ANSIBLE=1`; same full pytest suite | **98 passed**, Python 3.12.15. Git-less image uses explicit test-only source context; real Git builds were also checked. |
| Final I4B/API acceptance | From `apps/api`: `.venv/bin/python -m pytest tests/test_i4b_runtime.py tests/test_source_identity.py tests/test_capability_diagnostics.py -q --tb=short` with `ATLAS_TEST_DATABASE_URL` and `ATLAS_TEST_RUNTIME_PYTHON` | **28 passed** after final fixture regeneration: real control/callback/Runner, COMPLETE/PARTIAL, evidence/reconciliation, no unsafe absence, replay, malformed AIP, failure, limits, cancel and real probe diagnostics. |
| Real runtime regressions | Same three files plus `tests/test_i4a_runtime.py tests/test_i3_live_runtime.py`, same PostgreSQL/runtime environment | **58 passed**; actual I3 complete/partial/failure/malformed/missing/cancel and I4A version/collection isolation included. |
| Existing integration/discovery/reconciliation selector | `tests/test_integration_runtime.py`, `test_runtime_packaging.py`, `test_connector_packages.py`, `test_integration_catalogue_api.py`, `test_connector_lifecycle_api.py`, `test_connector_bootstrap.py`, `test_i2_runtime.py`, `test_i3_runtime.py`, `test_i4a_runtime.py`, `test_i2_integrations.py`, `test_i3_discovery.py`, `test_discovery_sync.py` | **277 passed, 1 skipped** when runtime-Python env was absent. The skipped exact-runtime version/resolution test subsequently passed in the 58-test selector and release-critical suite. |
| Release-critical | From `apps/api`: `bash ../../infra/ci/release-critical.sh` with API venv PATH, disposable PostgreSQL/Redis, pinned runtime Python and legacy plugin PYTHONPATH | **521 passed**, no skips. Includes unchanged legacy SDK/Proxmox tests and the new generic/candidate tests. |
| Contract and documentation regression | `PYTHONPATH=plugins/sdk:plugins/proxmox apps/api/.venv/bin/python -m pytest docs/architecture/integrations/contracts/tests apps/api/tests/test_repository_docs.py apps/api/tests/test_markdown_docs.py -q --tb=short` | **95 passed**; local links, untracked Markdown and whitespace included. Connector documentation checks are also included in its full suite. |
| Candidate/default builds | `python tools/build_bundle.py --candidate`; `python tools/build_bundle.py`; reproducible candidate/default/test bundles checked by full suite | Passed. Separate candidate output; normal manifest remains 0.1.0 probe-only. No release published. |
| Reviewed test collection provisioning | `python tools/test_collection.py --archive ../atlas/vendor/collections/community-proxmox-2.0.0.tar.gz --output <private-temporary-test-directory>` | Passed; exact archive SHA-256 verified before extraction. |
| Workflow lint | `actionlint .github/workflows/ci.yml .github/workflows/release.yml` in both writable repositories, actionlint executable from existing private CI cache | Passed, no diagnostics. |
| Python compilation | `python -m compileall -q` over changed Atlas modules/tests and Connector modules/tools/tests | Passed. |
| Migrations | From `apps/api`: `.venv/bin/python -m alembic heads` | One head: **20261012_0029**. No migrations added. |
| Diff checks | `git diff --check` in all three repositories | Passed. Atlas bootstrap diff is empty; SDK status is clean. |

Earlier harness/environment failures were resolved: protected collection namespace
loading inside AnsiballZ; explicit isolated taxonomy fixture setup; pinned Runner
PATH; missing disposable Redis; the disposable PostgreSQL listen-port setup;
and missing test tools/Git in the immutable runtime image. No production security
policy was weakened. Existing dependency deprecation
warnings are present. Frontend tests/build were not run because no UI changed.
No live Proxmox or Debian/systemd validation was run or claimed.

### Files changed

**atlas**

| Material file | Purpose |
| --- | --- |
| `apps/api/app/routes/integration_connections.py` | Return the scoped generic source-identity conflict before cancellation/mutation. |
| `apps/api/app/services/integration_connections.py` | Protect retained DataSource endpoints after successful discovery history. |
| `apps/api/app/services/integration_runtime.py` | Validate and forward additive bounded probe capability diagnostics. |
| `apps/runtime/ansible/atlas_runtime/probe.py` | Independently sanitize diagnostics and bound private probe output to 8 KiB. |
| `docs/architecture/integrations/contracts/integration-runtime.md` | Document the generic endpoint restriction and diagnostic field/bounds. |
| `docs/architecture/integrations/integration-roadmap.md` | Mark candidate implementation and preserve live-qualification gates. |
| `docs/product/feature-ledger.md` | Describe discovery as partial/candidate, with production still probe-only. |
| `infra/ci/release-critical.sh` | Include new generic and real candidate acceptance tests. |
| `apps/api/tests/fixtures/i4b/README.md` | Test-only harness bundle/metadata/ownership notes; excluded from production releases. |
| `apps/api/tests/fixtures/i4b/bundle.tar.gz` | Test-only harness bundle/metadata/ownership notes; excluded from production releases. |
| `apps/api/tests/fixtures/i4b/candidate-manifest.json` | Test-only harness bundle/metadata/ownership notes; excluded from production releases. |
| `apps/api/tests/fixtures/i4b/manifest.json` | Test-only harness bundle/metadata/ownership notes; excluded from production releases. |
| `apps/api/tests/test_capability_diagnostics.py` | Generic positive/hostile diagnostic regression coverage for both boundaries. |
| `apps/api/tests/test_i4b_runtime.py` | Real pinned runtime/AIP/PostgreSQL/reconciliation and cancellation/probe acceptance. |
| `apps/api/tests/test_source_identity.py` | Completed/partial/failed/cancelled history and tenancy/RBAC update coverage. |
| `docs/architecture/integrations/i4b-completion-report.md` | This completion evidence, file inventory and repository state. |

**atlas-connectors**

| Material file | Purpose |
| --- | --- |
| `.github/workflows/ci.yml` | Provision reviewed collection bytes and run actual Runner/candidate validation. |
| `README.md` | Document separate candidate/test builds and pinned test setup. |
| `connectors/proxmox/README.md` | Retain 0.1.0 boundary and link the unqualified candidate. |
| `connectors/proxmox/docs/capability-matrix.md` | Preserve I4A source review and identify the implemented follow-on. |
| `connectors/proxmox/docs/permissions.md` | Record whole-scope ACL proof, including unfiltered ACL audit. |
| `connectors/proxmox/docs/qualification.md` | State actual candidate status and remaining live qualification. |
| `requirements-dev.txt` | Pin collection/client/Runner development test dependencies. |
| `tools/build_bundle.py` | Explicit candidate packaging while excluding discovery/helpers from 0.1.0. |
| `connectors/proxmox/candidate/manifest.json` | Declare 0.2.0-i4b.1 unqualified scopes/classes/facts/entry points and exact dependency. |
| `connectors/proxmox/candidate/sbom.spdx.json` | Identify candidate and referenced reviewed runtime collection/licences/digest. |
| `connectors/proxmox/candidate/test_connection.yml` | Fixed bounded candidate readiness probe playbook. |
| `connectors/proxmox/discover.yml` | Fixed read-only discovery entry point. |
| `connectors/proxmox/docs/discovery.md` | Document source calls, transport, identities, mappings, facts and coverage. |
| `connectors/proxmox/docs/i4b-completion-report.md` | Record Connector ownership, validation boundary and live gates. |
| `connectors/proxmox/library/atlas_discover.py` | Ansible module entry into candidate orchestration. |
| `connectors/proxmox/library/atlas_readiness.py` | Bounded token/ACL readiness with sanitized capability diagnostics. |
| `connectors/proxmox/module_utils/atlas_discovery.py` | Collection orchestration, ACL/consistency proof, bounds and canonical NDJSON. |
| `connectors/proxmox/module_utils/atlas_normalization.py` | Stable identities, bounded AIP objects/facts and reliable current topology. |
| `connectors/proxmox/module_utils/atlas_transport.py` | Vetted/pinned authenticated Requests adapter, allowlists and raw-shape/flag checks. |
| `tests/conftest.py` | Load exact installed collection and explicit exported-source test context. |
| `tests/fixtures/proxmox/clustered.json` | Sanitized deterministic clustered base inventory and scenario definitions. |
| `tests/fixtures/proxmox/scenarios.json` | Sanitized deterministic clustered base inventory and scenario definitions. |
| `tests/proxmox_fixture_transport.py` | Inject deterministic source responses through the actual secured adapter. |
| `tests/test_documentation.py` | Discovery/identity/ACL/transport/real Runner/documentation regression coverage. |
| `tests/test_proxmox_ansible.py` | Discovery/identity/ACL/transport/real Runner/documentation regression coverage. |
| `tests/test_proxmox_capabilities.py` | Discovery/identity/ACL/transport/real Runner/documentation regression coverage. |
| `tests/test_proxmox_discovery.py` | Discovery/identity/ACL/transport/real Runner/documentation regression coverage. |
| `tests/test_proxmox_normalization.py` | Discovery/identity/ACL/transport/real Runner/documentation regression coverage. |
| `tests/test_proxmox_transport.py` | Discovery/identity/ACL/transport/real Runner/documentation regression coverage. |
| `tools/build_acceptance_fixture.py` | Reproducible separate test-only candidate-derived source harness. |
| `tools/test_collection.py` | Digest-verified test collection provisioning, outside production bundles. |

**atlas-connector-sdk**

No files changed; read-only SDK main remains clean.

### Final repository state

Expanded `git status --short -uall` (same changes as grouped `git status --short`):

**atlas**

```text
 M apps/api/app/routes/integration_connections.py
 M apps/api/app/services/integration_connections.py
 M apps/api/app/services/integration_runtime.py
 M apps/runtime/ansible/atlas_runtime/probe.py
 M docs/architecture/integrations/contracts/integration-runtime.md
 M docs/architecture/integrations/integration-roadmap.md
 M docs/product/feature-ledger.md
 M infra/ci/release-critical.sh
?? apps/api/tests/fixtures/i4b/README.md
?? apps/api/tests/fixtures/i4b/bundle.tar.gz
?? apps/api/tests/fixtures/i4b/candidate-manifest.json
?? apps/api/tests/fixtures/i4b/manifest.json
?? apps/api/tests/test_capability_diagnostics.py
?? apps/api/tests/test_i4b_runtime.py
?? apps/api/tests/test_source_identity.py
?? docs/architecture/integrations/i4b-completion-report.md
```

**atlas-connectors**

```text
 M .github/workflows/ci.yml
 M README.md
 M connectors/proxmox/README.md
 M connectors/proxmox/docs/capability-matrix.md
 M connectors/proxmox/docs/permissions.md
 M connectors/proxmox/docs/qualification.md
 M requirements-dev.txt
 M tools/build_bundle.py
?? connectors/proxmox/candidate/manifest.json
?? connectors/proxmox/candidate/sbom.spdx.json
?? connectors/proxmox/candidate/test_connection.yml
?? connectors/proxmox/discover.yml
?? connectors/proxmox/docs/discovery.md
?? connectors/proxmox/docs/i4b-completion-report.md
?? connectors/proxmox/library/atlas_discover.py
?? connectors/proxmox/library/atlas_readiness.py
?? connectors/proxmox/module_utils/atlas_discovery.py
?? connectors/proxmox/module_utils/atlas_normalization.py
?? connectors/proxmox/module_utils/atlas_transport.py
?? tests/conftest.py
?? tests/fixtures/proxmox/clustered.json
?? tests/fixtures/proxmox/scenarios.json
?? tests/proxmox_fixture_transport.py
?? tests/test_documentation.py
?? tests/test_proxmox_ansible.py
?? tests/test_proxmox_capabilities.py
?? tests/test_proxmox_discovery.py
?? tests/test_proxmox_normalization.py
?? tests/test_proxmox_transport.py
?? tools/build_acceptance_fixture.py
?? tools/test_collection.py
```

**atlas-connector-sdk**

```text
(empty — clean)
```
