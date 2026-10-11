# Atlas Ansible Runtime — I1

The isolated AGPL-3.0-only runtime serves private authenticated health,
capabilities and immutable package inspection. I1 has no execution endpoint,
vendor discovery, PostgreSQL connection, user session or Galaxy installation.
Atlas API uses HTTP and never imports Ansible.

`baseline.json` and `requirements.lock` identify the approved environment.
Every direct/transitive Python dependency is pinned; `pip --no-deps` plus
`pip check` prevents implicit dependency drift. Docker pins its Python base
image digest. Native installation creates `/opt/atlas/runtime-venv`; application
and runtime environments remain separate. An environment with missing/different
versions reports incompatible.

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
mount is read-only. Native store ownership is root; I1 ships catalogue metadata
without executable vendor bundles. Later official release installation must
use the privileged operator/package boundary.

`sbom.cdx.json` records all Python dependency versions, upstream licensing
metadata, reference wheel hashes and original notices under `notices/`.
Reference wheels are CPython 3.12 Linux x86_64; the inventory does not qualify
OS packages or every native architecture. Runtime GPL dependencies stay in
this process/environment boundary. Release/operator qualification of Docker,
native service lifecycle and image OS inventory remains necessary.
