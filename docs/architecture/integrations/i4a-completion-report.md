# I4A completion report — 12 October 2026

## Result and boundary

Implemented the Proxmox runtime dependency/capability groundwork only. Atlas
baseline is `atlas-ansible-i4a-v1` / **1.2.0**, runtime **0.3.1**. Ansible core
**2.19.7**, runner **2.4.3**, SDK **1.1.0** and AIP **1.0** remain unchanged.
Production Proxmox **0.1.0 remains probe-only**: discovery, scheduling and
complete snapshots disabled, no discovery entry point, no production collection
requirements. **Proxmox 9.2.11 remains UNQUALIFIED. I4 is not complete.**

**LIVE Docker/LXC acceptance for I4A is now COMPLETE. Native Debian/systemd
LIVE acceptance remains OUTSTANDING.** The post-merge operator evidence is
recorded separately below; I4A remains runtime/dependency groundwork only.

The original implementation created no fallback client, production inventory
implementation, migration, commit, push, merge or published release. Its package
tests constructed only non-publishable working-tree dry runs; its Docker images
were local validation images. The implementation file inventory and repository
state snapshots below describe that original work, not the subsequent live
deployment or this documentation update.

## Exact artefact and dependencies

Independently reviewed the downloaded Galaxy **community.proxmox 2.0.0** archive,
MANIFEST, FILES, runtime metadata, shared module utility and all five requested
shipped modules. It requires Ansible >=2.17.0 and lists 2.17–2.20 testing, so
Atlas 2.19.7 is within the declared range. The shared source enforces proxmoxer
>=2.3; its stale README install example is weaker. Requests is unbounded by
collection metadata. No other collection or HTTPS runtime library is required.

Archive SHA-256:
`77e02e0d1e341c6b064900fe58484ad8880cee4832f5fd65d09834ed068216f6`.

MANIFEST SHA-256:
`818c21db7b4b72ebf75bfe990eefb4c8499d02e6e599ede09a1dec99cdac88db`.

FILES SHA-256:
`b35b0110b5477a729d27763b2eacf3a862a3045e8c4e664614e44048d28389f2`.

Release source commit: `988661033eaba978379f1b47f5324200e262f974`, tag 2.0.0,
21 May 2026. Archive VM-info/shared-utility bytes also matched the exact release
commit. Galaxy supplies no signature and the annotated tag is unsigned; this
is reviewed immutable byte identity, not an independent upstream attestation.

Added exact Python pins: **proxmoxer 2.3.0, requests 2.34.2,
charset-normalizer 3.5.2, idna 3.20, urllib3 2.8.0, certifi 2026.7.22**.
The last four are required Requests transitives. Existing pins were retained.
No atlas-proxmox, httpx, SSH or optional developer extras were added. The complete
runtime has 27 Python pins, plus the independently hash-pinned SDK.

## Source calls, gaps and ACL implications

All paths below are GET reads under `/api2/json`. Every reviewed module first
reads `/version` in the shared constructor.

| Shipped module | Subsequent source calls |
| --- | --- |
| proxmox_cluster_status_info | `/cluster/status` |
| proxmox_node_info | `/nodes`; each node's `/nodes/{node}/network` and `/nodes/{node}/version` |
| proxmox_vm_info | `/cluster/resources?type=vm`; visible seeded nodes' `/nodes/{node}/qemu` and/or `/nodes/{node}/lxc`; optional `/nodes` validation; `config=current` reads `/nodes/{node}/{qemu|lxc}/{vmid}/config?current=1`; optional network reads QEMU `/agent/network-get-interfaces` or LXC `/interfaces` beneath that guest path |
| proxmox_storage_info | `/storage` (optional type filter) or the named `/storage/{storage}` route |
| proxmox_node_network_info | `/nodes` validation then `/nodes/{node}/network` (optional type filter); iface filtering is local; pending-change mode uses a raw session GET to the network endpoint |

The exact source-derived matrix and per-capability failure/completeness/ACL
analysis are in `atlas-connectors/connectors/proxmox/docs/capability-matrix.md`.
Node inventory is coupled to network/version reads and can abort on one offline
node. Guest/storage/bridge lists can silently omit unauthorized records. VM
seed records can survive without node-list enrichment/config. Named storage
errors collapse ACL/transport failures into a misleading nonexistence message.

A later contained per-node storage-status fallback is still required if that
capability is included: `/nodes/{node}/storage` and/or
`/nodes/{node}/storage/{storage}/status`. Independent node/version and per-guest
optional IP reads may also need isolation. Stable deployment identity requires
an explicit identity policy; cluster name/corosync IDs are not a durable UUID.
No fallback was implemented.

Official source review found Sys.Audit at `/` for cluster status, VM.Audit on
`/vms/{vmid}` for guest lists/config, Datastore.Audit on `/storage/{storage}`
for storage lists/status, and SDN.Audit (or broader SDN.Use) through
`/sdn/zones/localnetwork/{bridge}` for bridge visibility. The named storage
configuration route requires **Datastore.Allocate** and should be avoided in
favor of the read-only list route. Optional QEMU IP enrichment needs
VM.GuestAgent.Audit in the reviewed API; keep it outside base inventory.
Privilege-separated token permissions intersect with backing-user permissions.
These are reference-source findings, not qualification of any actual server.

HTTP 200/empty inventory never proves COMPLETE. Future I4 must prove effective
ACL/visibility and scope consistency. Existing fingerprint-before-credential,
DNS peer pinning, redirect rejection and response/deadline bounds must be
preserved through actual collection transport; a precheck followed by unpinned
Proxmoxer is unacceptable. This slice makes no production source calls.

## Runtime health, packaging and compatibility

A single Atlas-owned collection lock and vendored source archive feed Docker
and native installation. The generic packaging tool verifies archive, manifest,
file-manifest and every file digest before installation. Two internal archive
links are materialised as checked regular files; installed symlinks are refused.
The stricter untrusted Connector archive rules remain intact.

Health reads actual installed versions and verifies contents every time. Drift,
missing code, changed manifests, unreviewed collections and lock mismatch fail
closed. Bounded name/version/digest/state records expose no filesystem path or
raw command output. Atlas API validates and compares the health/capabilities
reports with its canonical baseline. Catalogue dependency matching uses exact
kind/name/version/digest. Python version maps do not invent artefact identities.

Protected paths are `/app/collections` (Docker) and
`/opt/atlas/apps/runtime/ansible/collections` (native), with system Python-path
collection scanning disabled. Both parent launchers and fixed workers supply
the protected environment, independent of job HOME/inherited PYTHONPATH.
Connector installation remains store-only and cannot install dependencies;
API staging and independent runtime inspection reject adjacent bundled
`collections` / `ansible_collections` that could shadow the protected path.

API/core gained no Proxmox import/call or vendor-specific logic. Existing
runtime-view/package-admin and customer/site Integration authorization remain
unchanged. There are no new routes, UI changes, database fields or migrations.
Collection health is an additive payload extension. Migration head remains
**20261012_0029**, single head. Production manifest and bundled probe bytes,
legacy plugins, SDK repository and AIP schemas are unchanged.

## Licences, notices and documentation

The runtime SBOM contains all 29 components: 27 Python dependencies, SDK and
collection. Original upstream notices were retained for community.proxmox
(GPL-3.0-or-later / BSD-2-Clause), proxmoxer (MIT), requests (Apache-2.0),
charset-normalizer (MIT), idna (BSD-3-Clause), urllib3 (MIT) and certifi
(MPL-2.0). The collection's unmodified archive includes source and copyright
headers. This follows accepted ADR 0003/0005/0006 and architecture v1.3;
no legacy AGPL implementation was copied into the Apache Connector.

Updated runtime/deployment docs, private health contract documentation, roadmap,
feature ledger and third-party notices. Added the dated runtime baseline review
and Connector capability, permissions and qualification documents. Only I4A's
internal dependency groundwork is marked Implemented; production inventory
remains Planned but not implemented.

## Executed validation

Commands used disposable local services/environments and generated test-only
credentials. No credential values are recorded here. Final evidence is retained
under `/private/tmp/atlas-i4a-validation`.

| Command / check actually executed | Final result |
| --- | --- |
| `python3 -m venv /private/tmp/atlas-i4a-runtime-venv`; exact SDK hash install; `pip install --no-deps -r apps/runtime/ansible/requirements.lock`; `pip check` | PASS; all pins installed; no broken requirements. Host is macOS Python 3.14.7; this is native-style environment validation, not Debian LIVE acceptance. |
| Shared offline collection installer into the staged native-style runtime; actual Runtime.health | PASS; healthy, community.proxmox 2.0.0, reviewed digest; repeat installation verified the same identity. |
| `ansible --version`; `ansible-galaxy collection list --format json` against protected staged path | PASS; core 2.19.7 and collection 2.0.0. Ansible's built-in `_protomatter` pseudo-collection is expected. |
| `docker build -f apps/runtime/ansible/Dockerfile -t atlas-runtime:i4a-validation .` | PASS; final image uses pinned Python base, Python 3.12.15 and reviewed offline collection. |
| Network-disabled, read-only, unprivileged Docker health / `pip check` / Ansible version / collection list / `ansible-doc --type module --json` for all five reviewed modules | PASS; healthy exact identity, all five modules resolved, no source connection. |
| `.venv/bin/python -m pytest tests ../../plugins/sdk/tests ../../plugins/proxmox/tests -q -rs --tb=short` with fresh PostgreSQL 17, disposable Redis and pinned runtime | **1,110 passed, 68 skipped**. All skips are nginx gateway tests requiring nginx >=1.28 / ATLAS_TEST_NGINX. I1–I3 database, real Redis, callback/cancellation and test-only real Ansible regressions ran. |
| `bash ../../infra/ci/release-critical.sh` from apps/api with its venv activated | **493 passed**; includes final I4A regressions and dry-run Docker/native package verification. |
| Connector `/private/tmp/atlas-connectors-build-venv/bin/python -m pytest -q --tb=short` | **24 passed**. |
| `apps/api/.venv/bin/python -m pytest docs/architecture/integrations/contracts/tests -q --tb=short` | **77 passed**. |
| Final dry-run reproducibility and Docker/native package-content checks after including review/report docs | **2 passed**. |
| Local Markdown link validation | **44 links in 12 files passed**, including the completion report. |
| `go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7` against Atlas and Connector CI/release workflows | PASS, no diagnostics. |
| `.venv/bin/python -m alembic heads` | PASS; `20261012_0029 (head)` only. |
| Baseline pin/SBOM/digest consistency; `git diff --check` | PASS. |
| SDK `git diff --exit-code`; legacy plugin/migration/bootstrap diffs | PASS; no changes. |

The initial full run had a Redis connection failure, resolved with a disposable
Redis service. Initial package checks exposed Galaxy PAX/internal links; the
reviewed-archive reader was corrected without weakening Connector validation.
Migration tests were rerun only with fresh empty databases after their explicit
safety preconditions were identified. The final results above have no failures.
Existing Python deprecation and temporary-store cleanup warnings remain.

## Post-merge LIVE Docker/LXC operator acceptance

Operator-confirmed acceptance was completed on the existing Atlas Docker test
LXC running merged `dev`. The deployed merged commit included the I4A runtime
baseline; the working tree was clean and matched `origin/dev`.

Deployment with `docker compose ... up -d --build` completed successfully:

| Service | Live deployment result |
| --- | --- |
| api | healthy |
| runtime | healthy |
| web | healthy |
| worker | running |
| postgres | healthy |
| redis | healthy |
| runtime-init | exited 0 |
| connector-bootstrap | exited 0 |

An initial ad-hoc `ansible-galaxy` invocation could not create
`/home/atlas-runtime/.ansible/tmp` in the hardened read-only runtime container.
This was an inspection-command failure, not a product failure. Re-running the
inspection with temporary Ansible state redirected to `/tmp` and
`ANSIBLE_COLLECTIONS_PATH=/app/collections` showed **community.proxmox 2.0.0**
from `/app/collections/ansible_collections`. The only other collection entry was
Ansible's expected internal `ansible._protomatter` pseudo-collection.

The canonical protected runtime endpoint `GET /v1/health` was called using the
existing runtime-control authentication mechanism without exposing the secret.
The live response reported:

| Field | Live value |
| --- | --- |
| state | `healthy` |
| runtime_version | `0.3.1` |
| protocol_version | `integration-runtime-v1` |
| baseline_id | `atlas-ansible-i4a-v1` |
| baseline_version | `1.2.0` |
| packaging_mode | `docker_compose` |
| ansible_core_version | `2.19.7` |
| ansible_runner_version | `2.4.3` |
| proxmoxer | `2.3.0` |
| requests | `2.34.2` |
| community.proxmox version | `2.0.0` |
| community.proxmox state | `compatible` |
| community.proxmox digest | `sha256:77e02e0d1e341c6b064900fe58484ad8880cee4832f5fd65d09834ed068216f6` |

The live digest matched the reviewed/pinned I4A collection identity.

Regression acceptance confirmed:

- The existing saved Proxmox Integration remained intact.
- Saved encrypted credentials remained usable.
- Test Connection succeeded without re-entering credentials.
- Production Proxmox discovery remained disabled as intended.
- **Proxmox 9.2.11 remains UNQUALIFIED.**

These checks record no Proxmox inventory discovery or source qualification.
**I4 is not complete.** Production discovery, scheduling and complete snapshots
remain disabled; I4A remains runtime/dependency groundwork only.

## Remaining qualification and limits

- No Proxmox source discovery or Proxmox 9.2.11 qualification; no COMPLETE
  visibility claim. Actual transport/ACL/source behavior remains future I4 work.
- Native Debian/systemd LIVE acceptance remains outstanding. Local package,
  macOS venv, Python 3.12 Docker validation and the completed live Docker/LXC
  acceptance do not replace that gate.
- The 68 nginx integration tests were skipped because the required local nginx
  binary was unavailable; no frontend build was run because no UI changed.
- The Python lock retains the existing exact-version convention. Reference
  wheel hashes are SBOM evidence, not a cross-platform hash-enforced wheel lock.
  The collection archive/manifests/content are hash-enforced. OS/image SBOM and
  final redistribution qualification remain release gates.

## Every material file changed

### Atlas

| File | Purpose |
| --- | --- |
| `THIRD-PARTY-NOTICES.md` | Truthful I4A scope, provenance, deployment, contract or qualification documentation. |
| `apps/api/app/services/connector_catalogue.py` | Generic sanitized collection health or exact catalogue dependency compatibility. |
| `apps/api/app/services/connector_store.py` | Refuse Connector-bundled collection shadowing paths. |
| `apps/api/app/services/integration_runtime.py` | Generic sanitized collection health or exact catalogue dependency compatibility. |
| `apps/api/tests/test_i2_runtime.py` | Installed identity, compatibility, packaging or protected-environment regressions. |
| `apps/api/tests/test_i3_runtime.py` | Installed identity, compatibility, packaging or protected-environment regressions. |
| `apps/api/tests/test_integration_runtime.py` | Installed identity, compatibility, packaging or protected-environment regressions. |
| `apps/api/tests/test_runtime_packaging.py` | Installed identity, compatibility, packaging or protected-environment regressions. |
| `apps/runtime/ansible/Dockerfile` | Offline digest-verified collection installation and protected search path. |
| `apps/runtime/ansible/README.md` | Truthful I4A scope, provenance, deployment, contract or qualification documentation. |
| `apps/runtime/ansible/atlas_runtime/discovery_worker.py` | Actual collection health or protected probe/discovery child environment. |
| `apps/runtime/ansible/atlas_runtime/jobs.py` | Actual collection health or protected probe/discovery child environment. |
| `apps/runtime/ansible/atlas_runtime/probe.py` | Actual collection health or protected probe/discovery child environment. |
| `apps/runtime/ansible/atlas_runtime/probe_worker.py` | Actual collection health or protected probe/discovery child environment. |
| `apps/runtime/ansible/atlas_runtime/server.py` | Actual collection health or protected probe/discovery child environment. |
| `apps/runtime/ansible/baseline.json` | Exact runtime pins, immutable collection identity and canonical baseline. |
| `apps/runtime/ansible/requirements.lock` | Exact runtime pins, immutable collection identity and canonical baseline. |
| `apps/runtime/ansible/sbom.cdx.json` | Inventory every added distributed component, licence, notice and artefact digest. |
| `docs/architecture/integrations/contracts/integration-runtime.md` | Truthful I4A scope, provenance, deployment, contract or qualification documentation. |
| `docs/architecture/integrations/integration-roadmap.md` | Truthful I4A scope, provenance, deployment, contract or qualification documentation. |
| `docs/deployment/integration-runtime.md` | Truthful I4A scope, provenance, deployment, contract or qualification documentation. |
| `docs/product/feature-ledger.md` | Truthful I4A scope, provenance, deployment, contract or qualification documentation. |
| `infra/ci/release-critical.sh` | Add I4A regression tests to the release-critical selector. |
| `infra/install/native.py` | Run the same offline collection installer in the native runtime venv. |
| `infra/release/package-manifest.json` | Include and independently verify the reviewed runtime artefacts in both package formats. |
| `infra/release/release.py` | Include and independently verify the reviewed runtime artefacts in both package formats. |
| `infra/systemd/atlas-runtime.service` | Protected collection path, no sys.path collection scan, no generated bytecode. |
| `apps/api/tests/test_i4a_runtime.py` | Installed identity, compatibility, packaging or protected-environment regressions. |
| `apps/runtime/ansible/atlas_runtime/collections.py` | Shared offline installer and installed-content verifier. |
| `apps/runtime/ansible/collections.lock.json` | Exact runtime pins, immutable collection identity and canonical baseline. |
| `apps/runtime/ansible/notices/certifi/LICENSE` | Original upstream licence/notice material. |
| `apps/runtime/ansible/notices/charset-normalizer/LICENSE` | Original upstream licence/notice material. |
| `apps/runtime/ansible/notices/community.proxmox/COPYING` | Original upstream licence/notice material. |
| `apps/runtime/ansible/notices/community.proxmox/LICENSES/BSD-2-Clause.txt` | Original upstream licence/notice material. |
| `apps/runtime/ansible/notices/community.proxmox/LICENSES/GPL-3.0-or-later.txt` | Original upstream licence/notice material. |
| `apps/runtime/ansible/notices/community.proxmox/REUSE.toml` | Original upstream licence/notice material. |
| `apps/runtime/ansible/notices/idna/LICENSE.md` | Original upstream licence/notice material. |
| `apps/runtime/ansible/notices/proxmoxer/LICENSE.txt` | Original upstream licence/notice material. |
| `apps/runtime/ansible/notices/requests/LICENSE` | Original upstream licence/notice material. |
| `apps/runtime/ansible/notices/requests/NOTICE` | Original upstream licence/notice material. |
| `apps/runtime/ansible/notices/urllib3/LICENSE.txt` | Original upstream licence/notice material. |
| `docs/architecture/integrations/i4a-completion-report.md` | Truthful I4A scope, provenance, deployment, contract or qualification documentation. |
| `docs/architecture/integrations/i4a-runtime-baseline.md` | Truthful I4A scope, provenance, deployment, contract or qualification documentation. |
| `vendor/collections/README.md` | Reviewed original source archive and vendor ownership notes. |
| `vendor/collections/community-proxmox-2.0.0.tar.gz` | Reviewed original source archive and vendor ownership notes. |

### atlas-connectors

- `connectors/proxmox/README.md`: dated source calls, privileges, qualification boundary or index links.
- `connectors/proxmox/docs/capability-matrix.md`: dated source calls, privileges, qualification boundary or index links.
- `connectors/proxmox/docs/permissions.md`: dated source calls, privileges, qualification boundary or index links.
- `connectors/proxmox/docs/qualification.md`: dated source calls, privileges, qualification boundary or index links.

### atlas-connector-sdk

No files changed. Read-only main remains at `8b0518c462289cca4758c3b9bf362f1130928a1c`.

## Repository state (`git status --short`)

atlas:

```text
 M THIRD-PARTY-NOTICES.md
 M apps/api/app/services/connector_catalogue.py
 M apps/api/app/services/connector_store.py
 M apps/api/app/services/integration_runtime.py
 M apps/api/tests/test_i2_runtime.py
 M apps/api/tests/test_i3_runtime.py
 M apps/api/tests/test_integration_runtime.py
 M apps/api/tests/test_runtime_packaging.py
 M apps/runtime/ansible/Dockerfile
 M apps/runtime/ansible/README.md
 M apps/runtime/ansible/atlas_runtime/discovery_worker.py
 M apps/runtime/ansible/atlas_runtime/jobs.py
 M apps/runtime/ansible/atlas_runtime/probe.py
 M apps/runtime/ansible/atlas_runtime/probe_worker.py
 M apps/runtime/ansible/atlas_runtime/server.py
 M apps/runtime/ansible/baseline.json
 M apps/runtime/ansible/requirements.lock
 M apps/runtime/ansible/sbom.cdx.json
 M docs/architecture/integrations/contracts/integration-runtime.md
 M docs/architecture/integrations/integration-roadmap.md
 M docs/deployment/integration-runtime.md
 M docs/product/feature-ledger.md
 M infra/ci/release-critical.sh
 M infra/install/native.py
 M infra/release/package-manifest.json
 M infra/release/release.py
 M infra/systemd/atlas-runtime.service
?? apps/api/tests/test_i4a_runtime.py
?? apps/runtime/ansible/atlas_runtime/collections.py
?? apps/runtime/ansible/collections.lock.json
?? apps/runtime/ansible/notices/certifi/
?? apps/runtime/ansible/notices/charset-normalizer/
?? apps/runtime/ansible/notices/community.proxmox/
?? apps/runtime/ansible/notices/idna/
?? apps/runtime/ansible/notices/proxmoxer/
?? apps/runtime/ansible/notices/requests/
?? apps/runtime/ansible/notices/urllib3/
?? docs/architecture/integrations/i4a-completion-report.md
?? docs/architecture/integrations/i4a-runtime-baseline.md
?? vendor/collections/
```

atlas-connectors:

```text
 M connectors/proxmox/README.md
?? connectors/proxmox/docs/
```

atlas-connector-sdk:

```text
(empty — clean)
```
