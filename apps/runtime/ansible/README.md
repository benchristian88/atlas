# Atlas Ansible Runtime — I4A dependency baseline

The isolated AGPL-3.0-only runtime serves private authenticated health,
capabilities, immutable package inspection, bounded probes and the existing I3
discovery-job substrate. Production Proxmox remains probe-only; no production
inventory is implemented. The runtime has no PostgreSQL connection or user session.
Atlas API uses HTTP and never imports Ansible.

`baseline.json` and `requirements.lock` identify the approved environment.
Every direct/transitive Python dependency is pinned; `pip --no-deps` plus
`pip check` prevents implicit dependency drift. Docker pins its Python base
image digest. Native installation creates `/opt/atlas/runtime-venv`; application
and runtime environments remain separate. An environment with missing/different
versions reports incompatible.

`collections.lock.json` pins reviewed community.proxmox 2.0.0 by archive,
MANIFEST and FILES SHA-256. Docker/native packaging both install the original
vendored archive offline using `atlas_runtime.collections`. Health verifies the
actual installed version and every file; it reports bounded version/digest/state
and fails closed on drift. `ANSIBLE_COLLECTIONS_PATH` is fixed to this runtime's
`collections` directory and `ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=False`; both fixed
workers enforce it independently of ephemeral HOME/inherited Python paths.
Connector packages cannot bundle adjacent collections or install dependencies.
There is no runtime Galaxy download or package-install control operation.

Baseline 1.2.0 / runtime 0.3.1 adds proxmoxer 2.3.0, requests 2.34.2,
charset-normalizer 3.5.2, idna 3.20, urllib3 2.8.0 and certifi 2026.7.22.
Ansible core 2.19.7 / runner 2.4.3 and SDK 1.1.0 remain unchanged. See the
[dated I4A review](../../../docs/architecture/integrations/i4a-runtime-baseline.md)
for source evidence, licence boundaries and capability gaps. Proxmox 9.2.11
remains unqualified and production discovery stays disabled. I4 is incomplete.

Compose creates the control credential once in `runtime_control`, using a
one-shot provisioner with no network. API and runtime mount it read-only; the
runtime has no host port. It uses the internal `runtime_private` network for
authenticated API control and a dedicated, non-internal `runtime_source` bridge
for outbound source connectivity. Only runtime joins the source bridge; its
read-only mounts/root filesystem, dropped capabilities and no-new-privileges
remain enforced. Native
installation creates `/etc/atlas-runtime/control.secret` root-owned, readable
only by the dedicated control group. The dedicated runtime account cannot read
Atlas's database/authentication configuration. Existing credentials and store
state survive upgrades. Native binds loopback independently of inherited host
variables. `--manual-only` is supported by both installers.

The runtime independently checks Connector identity, archive SHA-256, embedded
manifest, verification receipt and every immutable extracted file. The store
mount is read-only. Native store ownership is root. The reviewed 0.1.0 probe
bootstrap remains the sole production Proxmox executable bundle; later discovery
release installation must use the same privileged operator/package boundary.

`sbom.cdx.json` records the collection and all Python dependency versions, upstream licensing
metadata, reference wheel hashes and original notices under `notices/`.
Reference wheels are CPython 3.12 Linux x86_64; the inventory does not qualify
OS packages or every native architecture. Runtime GPL dependencies stay in
this process/environment boundary. Release/operator qualification of Docker,
native service lifecycle and image OS inventory remains necessary.
