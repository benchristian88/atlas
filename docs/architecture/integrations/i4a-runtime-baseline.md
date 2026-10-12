# I4A — reviewed Proxmox runtime dependency baseline

Review date: **12 October 2026**. I4A establishes dependencies and generic
collection health/compatibility. **I4 is not complete. Proxmox 9.2.11 remains
UNQUALIFIED; production Proxmox 0.1.0 remains probe-only**, with discovery,
scheduling and complete snapshots disabled. SDK 1.1.0/AIP 1.0 and I3
orchestration/reconciliation/snapshot semantics are unchanged.

## Reviewed identities

Runtime baseline `atlas-ansible-i4a-v1`, version **1.2.0**, runtime **0.3.1**,
retains ansible-core **2.19.7**, ansible-runner **2.4.3** and the pinned Python
3.12 Docker base. Native uses the existing dedicated runtime venv.

[collections.lock.json](../../../apps/runtime/ansible/collections.lock.json)
records community.proxmox **2.0.0**, its archive/manifest/file-manifest SHA-256s,
release tag/source commit, source URL, compatibility metadata and licences.
The original [Galaxy archive](https://galaxy.ansible.com/api/v3/plugin/ansible/content/published/collections/artifacts/community-proxmox-2.0.0.tar.gz)
is vendored under `vendor/collections`; archive SHA-256 is
`77e02e0d1e341c6b064900fe58484ad8880cee4832f5fd65d09834ed068216f6`.
The reviewed [source commit](https://github.com/ansible-collections/community.proxmox/tree/988661033eaba978379f1b47f5324200e262f974)
is `988661033eaba978379f1b47f5324200e262f974`, release tag 2.0.0 (21 May 2026).
Galaxy supplies no archive signature; the annotated Git tag is unsigned.
Do not describe this reviewed digest as upstream attestation verification.

The shipped runtime metadata requires Ansible >=2.17.0; its README lists
testing across 2.17–2.20. Shared module source requires proxmoxer >=2.3,
despite a stale >=2.0 README install example. Requests has no collection-imposed
version bound. No other collection dependencies are declared.

| Added Python pin | Reason | Licence |
| --- | --- | --- |
| proxmoxer 2.3.0 | Required shared module library; HTTPS backend | MIT |
| requests 2.34.2 | HTTPS backend required by proxmoxer | Apache-2.0 |
| charset-normalizer 3.5.2 | Requests required transitive, >=2,<4 | MIT |
| idna 3.20 | Requests required transitive, >=2.5,<4 | BSD-3-Clause |
| urllib3 2.8.0 | Requests required transitive, >=1.26,<3 | MIT |
| certifi 2026.7.22 | Requests required transitive, >=2023.5.7 | MPL-2.0 |

These exact available releases were checked through upstream PyPI metadata and
the downloaded wheel METADATA/licence files. No SSH, SOCKS, developer extras,
legacy atlas-proxmox or httpx are introduced. The existing exact
[requirements.lock](../../../apps/runtime/ansible/requirements.lock) and baseline
remain canonical; `--no-deps` and `pip check` prevent implicit resolver changes.
The Python lock follows the existing exact-version installation convention;
SBOM reference wheel hashes are inventory evidence, not a cross-platform
hash-enforced Python wheel lock. The collection itself is hash-enforced offline.

## Packaging and search path

Both Docker and native installation run the same generic
`atlas_runtime.collections` packaging tool against the vendored archives. It
checks the archive SHA-256 before bounded decompression/parsing, checks immutable
MANIFEST/FILES identities and every file digest, then installs regular read-only
files. The reviewed Galaxy archive's two internal symlinks are materialised as
regular files matching FILES.json; no filesystem symlinks are installed. PAX
metadata is accepted only for the already digest-verified vendor artefact. The
stricter untrusted Connector archive policy is unchanged.

The fixed search path is `/app/collections` in Docker and
`/opt/atlas/apps/runtime/ansible/collections` in native, with layout
`ansible_collections/{namespace}/{name}`. `ANSIBLE_COLLECTIONS_PATH` is set
explicitly and `ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=False` excludes unrelated
Python-path collections. Both fixed Ansible workers set these values themselves,
so ephemeral HOME and inherited environment cannot select a different collection
path. Connector archives cannot include top-level `collections` or
`ansible_collections`; API installation and runtime independent inspection both
reject those paths, preventing adjacent-playbook collection shadowing.

Only Atlas packaging owns this dependency set. Runtime has no installation
endpoint or Galaxy download. Connector installation stages its verified files
into the existing store; a dependency declaration can request compatibility but
cannot install packages or mutate the runtime. Supported deployments keep
runtime code/venv/collections outside its writable workspace. Legacy plugin
metadata/PYTHONPATH is excluded by existing child-environment allowlists.

## Generic health and catalogue compatibility

Health reads actual installed MANIFEST versions and verifies every installed
file against pinned FILES.json identities; altered/deleted/additional files,
symlinks, unexpected collections, a changed manifest/version or collection-lock
drift fail closed.
No mutable installed receipt is accepted as identity proof. A public collection
record contains only bounded name, installed version (or null), verified archive
digest (or null), and `compatible`/`incompatible` state. Digest is reported only
when all installed bytes match the reviewed archive's immutable manifests.

Atlas API validates the bounded collection records and requires its baseline,
the actual health report and capability report to agree. It forwards no path,
raw command output or unvalidated data. Catalogue compatibility uses this
canonical collection identity to compare manifest kind/name/version/digest.
Missing, wrong or unverified identity cannot satisfy a dependency. Existing
dependency-list consumers remain supported. Python version maps alone still
cannot satisfy a manifest requiring a Python artefact digest.

This stays vendor-neutral: no Proxmox import, API call or branch exists in Atlas
core. Existing runtime-view/package-administration RBAC and scoped Integration
permissions remain authoritative; there are no new routes or database fields.
The private collection-health payload is additive. No migrations are required.

## Capabilities and qualification

The Connector's [source-derived capability/call/ACL matrix](https://github.com/benchristian88/atlas-connectors/blob/feature/i4-proxmox-discovery/connectors/proxmox/docs/capability-matrix.md),
permissions and qualification docs cover all five required shipped modules.
Notable findings include a shared `/version` read, node inventory coupled to
network/version reads, permission-filtered guest/storage/bridge lists, the named
storage route's Datastore.Allocate requirement and missing contained per-node
storage status. Optional guest-agent IP calls must remain outside base coverage.
No complete scope is proven by an empty HTTP 200 response.

Collection transport does not yet preserve Atlas's fingerprint/DNS peer pinning,
redirect and response bounds. Future I4 must solve and test that inside the
isolated runtime; I4A makes no source calls. No fallback client or production
discovery entry point is added. The production manifest remains dependency-free
so current 0.1.0 probes continue on earlier baselines; test manifests prove the
new exact collection contract.

## Distribution licences

ADR 0003/0005/0006 and architecture v1.3 retain the separate runtime/Connector
boundary. community.proxmox remains GPL-3.0-or-later with BSD-2-Clause material;
the original archive includes source, copyright headers and licence texts.
Original Python notices, including certifi's MPL-2.0 licence, are retained under
runtime `notices/`. The runtime CycloneDX SBOM includes every new distributed
component, exact version and reference artefact digest; its scope now covers
the collection plus Python wheels. This is not a final OS/image licence audit.
No AGPL legacy plugin code is copied into the Apache-licensed Connector.

## Validation limits

See the [I4A completion report](i4a-completion-report.md) for executed commands
and outcomes. Native-style environment/package validation does not qualify a
live Debian/systemd installation. No live Proxmox discovery, source ACL proof,
or Proxmox 9.2.11 qualification is claimed.
