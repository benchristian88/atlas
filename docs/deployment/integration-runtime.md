# Local integration runtime and Connector catalogue

Discovery diagnostics use a runtime-created private sidecar, parsed on terminal
paths before workspace cleanup and returned through authenticated job status.
No user-selected trace destination or raw log stream is accepted. Debug is armed
for one Integration's next run only, with administrator-only access and 48-hour
expiry. The existing worker purges stored debug rows; portable backups exclude
them. Deploy API/worker migration `20261018_0030` and the matching runtime together.
Older Connectors remain compatible and report diagnostics unavailable. See
[discovery operations](discovery-runs.md) and the
[diagnostic contract](../architecture/integrations/discovery-diagnostics.md).

Normal Docker Compose and native/systemd installations include an isolated Atlas
Ansible Runtime. Open **Integrations → Catalogue** to inspect the bundled offline
catalogue, or **Runtime** with a global runtime-view grant to inspect health,
versions and the approved dependency baseline. The browser calls Atlas API;
it never connects directly to the runtime.

I4A runtime baseline 1.2.0 packages the reviewed **community.proxmox 2.0.0**
archive and exact proxmoxer/requests dependencies. They belong to Atlas runtime
packaging; Connector installation cannot install dependencies. The fixed
collection path is `/app/collections` (Docker) or
`/opt/atlas/apps/runtime/ansible/collections` (native), independent of job HOME
and Python-path collection scanning. Health verifies actual installed file
identity against the collection lock and reports sanitized version/digest/state.
See the [dated baseline review](../architecture/integrations/i4a-runtime-baseline.md)
for all pins, search-path rules and source/licence evidence. **Production
discovery stays disabled and Proxmox 9.2.11 stays unqualified.**

I2 includes a hash-pinned local Proxmox VE 0.1.0 **Test Connection-only**
package. Its source-version qualification is explicitly unqualified; no inventory
or AIP is produced. Docker + Compose and UniFi Network remain metadata only.
Install the approved package as a global package administrator, then use **Add
integration** with Customer/Site-scoped `integrations.manage` permission. Runtime
health and package compatibility must pass before activation/configuration.
Remote executable installation still fails closed pending GitHub/Sigstore
qualification. No archive upload, download URL, Git, playbook or Galaxy input exists.

## Configure and test

Choose an authorized Customer/Site, name and installed Connector. Forms use the
verified Manifest, including its secret markers, required fields and TLS condition.
Both Proxmox token identity and token secret are write-only. Use a dedicated API
token; password/root login is unsupported. No real credential belongs in a command,
fixture, screenshot or support log. Saved forms show Configured/Not configured and
provide full **Replace credentials** or explicit **Clear credentials** actions.
Clearing leaves the connection unconfigured; it does not remove its DataSource.
Disabling preserves config/credentials. Removal destroys live credentials and
retires the Integration while retaining provenance/history.

`integrations.run` authorizes Test Connection within the same Customer/Site.
An unsaved preview also requires manage permission and stores only safe audit
metadata. A saved test persists a sanitized result/version; it creates no inventory,
evidence, DiscoveryRun or AIP state. Supported/untested/incompatible derives from
the exact Manifest; Proxmox I2 results remain untested until I4 qualification.
Probe-only versions have no Run Now or scheduling controls. Generic discovery-capable
versions use the [discovery operator workflow](discovery-runs.md); no production
discovery-capable Connector is currently shipped.

An explicit [local operator qualification procedure](connector-qualification.md)
can stage one exact unqualified prerelease in a separate test instance/store.
It is unavailable through catalogue/customer installation APIs and does not change
production bootstrap, source qualification or the ordinary rejection policy.

TLS verifies certificates by default. For a self-signed deployment, choose
fingerprint and obtain the SHA-256 certificate fingerprint through a trusted
channel; it is checked before token transmission. An explicit insecure exception
is visibly warned and is never an automatic fallback. HTTPS is mandatory. Userinfo,
query/fragment, redirect following, loopback/link-local/metadata endpoints and
invalid ports are refused. Private LAN/ULA addresses are allowed. DNS results are
checked and the connection uses a vetted numeric peer with the original TLS
hostname; ambient proxy settings are ignored. Calls are bounded and cannot walk
inventory. The token-permissions endpoint and version endpoint alone are probed.

Taxonomy mappings are global per Connector/version. **Resolve mappings** is
available only to global package administrators and selects existing active
reference types. Only exact stable-key recommendations auto-map. Required
unresolved mappings block activation/use; optional Manifest declarations can be
explicitly ignored. No reference types are created by a Connector. Package updates
validate dependent config/scopes/credential field presence without decrypting
secrets and preserve the active tuple if changes require configuration.

Source credentials use the existing `ATLAS_DATA_ENCRYPTION_KEY` and encrypted
backup/restore rewrap. Retain that key under the normal operator lifecycle. A raw
SQL dump contains ciphertext but cannot migrate it to an unrelated key; use
[encrypted backup/restore](backup-restore.md). After restore, revalidate installed
package bytes/trust and runtime baseline before testing. Control secrets and
source keys never appear in normal responses.

## Deployment and authentication

Docker attaches `runtime` to two dedicated bridge networks:

- `runtime_private` has `internal: true` and carries authenticated API-to-runtime
  control and runtime-to-API callback traffic. API, worker and runtime join it.
- `runtime_source` is a normal outbound-routing bridge (`internal: false`) for
  reaching source infrastructure. Only runtime joins it; PostgreSQL, Redis,
  gateway, web, worker and API do not join it.

The source bridge supplies the outbound gateway that an internal-only runtime
lacks. It does not publish a runtime port or give the container a direct LAN
address; only the existing nginx gateway exposes Atlas. Every runtime-control
request still requires the independent control credential. The runtime keeps a
read-only root filesystem and read-only control/store mounts, drops all Linux
capabilities and uses `no-new-privileges`. It has no host networking, privileged
mode, `NET_ADMIN`, Docker socket or broad host mount.

The runtime receives no PostgreSQL, Redis or user/session credentials. Source
credentials arrive only for a bounded probe or discovery job through authenticated
private control transport and are removed after execution. A networkless one-shot provisioner creates a random 384-bit control
credential in the durable `runtime_control` volume. API and runtime mount that
volume read-only; worker also has a read-only mount for private dispatch. Existing valid material is preserved and invalid existing
material is refused.

Native installs create a separate `/opt/atlas/runtime-venv` with pinned Python
dependencies, and `atlas-runtime.service` under the dedicated `atlas-runtime`
account. The listener is fixed to `127.0.0.1:8091`; Docker or Podman is not required.
The separate control credential is `/etc/atlas-runtime/control.secret`, owned by
root, group `atlas-runtime-control`, mode `0640`, inside a `0750` directory. API
worker and runtime have that supplementary reader group. The runtime never receives
`/etc/atlas/atlas.env` or database authentication material.

Every health, capability and package-inspection request authenticates with this
independent control credential. It is never shown by normal UI/API responses or
logs. Protect and retain it across upgrade/reinstall; neither installer silently
rotates an existing valid value. Source credentials have separate scoped ownership. API provisions a separate
installation-local run-ingestion signing file; API/worker read it, while runtime
receives only the expiring run token. See [I3 implementation](../architecture/integrations/i3-implementation.md).

## Failure and manual-only operation

Health/control requests have a three-second timeout; Test Connection has a
28-second API deadline and a 22-second child-process deadline. Results are bounded
and sanitized. Four concurrent probes are allowed. A private 0700 workspace uses
0600 input/result files and suppressed Ansible events/output; process completion,
failure and timeout remove it, and startup cleans abandoned owned probe directories.
An outage produces **Unavailable**; a changed protocol/dependency baseline produces
**Incompatible**. Accepted Atlas knowledge remains usable in either state.
Runtime startup/readiness failures are reported without preventing core API/web
installation health and setup hand-off. Discovery jobs use private start/status/cancel
control, a ten-minute deadline, four concurrent slots and fixed API callbacks.
Ansible descendant sessions are frozen/terminated before root cleanup; Docker init
reaps orphaned descendants. Runtime memory/tasks and temporary output are bounded.

Both fresh installers support explicit opt-out:

```bash
python3 infra/install/compose.py --manual-only
sudo python3 infra/install/native.py --manual-only
```

This persists `ATLAS_RUNTIME_ENABLED=false`. Native disables the runtime unit;
Compose starts the core service set without the runtime. Upgrades preserve that
setting. Runtime source/dependency packaging remains part of the release.

Inspect service health without printing credentials:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml ps
systemctl status atlas-runtime
journalctl -u atlas-runtime
```

Use the applicable command for your deployment method. Do not publish port 8091,
give the runtime PostgreSQL access or add arbitrary writable source/socket mounts.

## Docker source-connectivity verification

Apply the updated Compose file in the existing deployed checkout. Reuse the
existing environment file, project name and override files; these examples run
from the checkout root with `.env` and the default `atlas` project. Recreate only
runtime and its one-shot prerequisites to apply network membership and stage the
packaged Connector while preserving the running API, control credential and
Connector store. A container restart alone does not apply the network change.

```bash
atlas_compose() {
  docker compose --env-file .env -f infra/docker/docker-compose.yml "$@"
}
atlas_compose config --quiet
atlas_compose build runtime runtime-init connector-bootstrap
atlas_compose up -d --force-recreate --wait --wait-timeout 60 runtime

atlas_runtime_id="$(atlas_compose ps -q runtime)"
docker inspect "$atlas_runtime_id" --format 'Networks={{range $name, $network := .NetworkSettings.Networks}}{{$name}} {{end}}Ports={{json .NetworkSettings.Ports}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}'
docker network inspect atlas_runtime_private atlas_runtime_source --format '{{.Name}} internal={{.Internal}} containers={{range .Containers}}{{.Name}} {{end}}'

atlas_compose exec -T runtime python - <<'PY'
import socket
with socket.create_connection(("192.168.99.28", 8006), timeout=5):
    print("TCP connected to 192.168.99.28:8006")
PY

atlas_compose exec -T api python - <<'PY'
import urllib.error
import urllib.request
request = urllib.request.Request("http://runtime:8091/v1/health")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:
    opener.open(request, timeout=5)
except urllib.error.HTTPError as error:
    assert error.code == 401, error.code
    print("Unauthenticated runtime health: HTTP 401")
else:
    raise SystemExit("FAIL: runtime health accepted an unauthenticated request")
PY
```

Expect both runtime networks, `Ports={}`, `ReadonlyRootfs=true`, `CapDrop=["ALL"]`
and `no-new-privileges:true`. The private network must report `internal=true`
with API, worker and runtime; the source network must report `internal=false` with only
runtime. Check **Integrations → Runtime** is healthy after recreation. The socket
probe proves outbound TCP reachability only; it uses no source credentials and
does not test TLS, Proxmox authentication or discovery. Record live connectivity
as passed only after this probe succeeds in the operator's deployment. If it
still fails, investigate the LXC/host route and firewall using the exact error.

## Protected packages and compatibility

Docker installs/upgrades start `runtime-init` to provision the control credential
and volume permissions, then the distinct one-shot `connector-bootstrap` service
runs `python -m scripts.stage_integration_bootstrap` from the API image. It has
`network_mode: none`, no database/authentication credentials, and only the
`connector_store` volume mounted writable. UID/GID 10001 match the API/store owner,
including its protected installation lock; native staging still requires root.
The existing catalogue verifier and `PackageStore.install` authenticate the
release-approved Proxmox 0.1.0 ID/version/digest and stage its immutable layout
offline. No database activation occurs. A global administrator still activates
the package through the Catalogue.

The runtime waits for successful staging and mounts the store read-only. Staging
failure exits nonzero and prevents runtime startup; API/knowledge startup remains
independent. Repeated staging verifies existing bytes and preserves them. Tampered
bundles or stored contents fail closed instead of being replaced silently. Avoid
`--no-deps` when applying this packaging fix, because that skips both prerequisites.

Catalogue content is release-packaged JSON; PostgreSQL records only the active
installed identity and safe verification/baseline metadata. Packages are global,
with one active version per Connector. `integration_runtime.manage` must be held
globally; scoped `integrations.manage` never authorizes executable installation.
All live configured connections, including disabled connections, block removal.
Package removal never deletes Assets, runs, assertions, evidence or Changes.

The store is `/var/lib/atlas-connectors`. Native ownership is root with API/runtime read-only access through the existing
control-reader group. The root installer stages fixed approved bootstrap packages
using the same verifier; administrator activation verifies an existing exact tuple
without acquiring store write access. Missing packages require a reviewed operator
package update, and native filesystem removal remains operator-owned. Docker exposes a writable store only to
trusted Atlas package-management code; the runtime's mount is read-only.
Exact identity, SHA-256, approved bootstrap allowlist/provenance, Manifest schema,
embedded metadata and bounded plain USTAR contents are checked before atomic
publication. The runtime independently checks the archive and extracted hashes.
Uninstall first quarantines all versions of the Connector and removes database
authority atomically, then completes file cleanup; rollback restores the address
if the transaction fails. Prior inactive immutable versions support explicit
catalogue-driven rollback while installed; uninstall removes their code too.
No automatic version activation occurs.

Official catalogue-selected remote installation remains disabled: provenance
verification exists, but catalogue package eligibility/installation authority is
still separate. The [local signed release acceptance procedure](local-release-acceptance.md)
adds explicit root authority only in a bound isolated test instance; it changes
neither production catalogue eligibility nor prerelease qualification. There is
no skip-verification switch. Bundled packages, when qualified
and shipped later, require exact digests bound to the trusted Atlas release.
The current offline catalogue needs no Internet connection and ships one exact
Proxmox probe archive produced in `atlas-connectors`. Its bootstrap digest is bound
to the Atlas release; this is local qualification, not remote attestation proof.

The approved environment identifies runtime `0.3.1`, protocol
`integration-runtime-v1`, baseline `atlas-ansible-i4a-v1` version `1.2.0`,
ansible-core `2.19.7` and ansible-runner `2.4.3`. All twenty-seven runtime Python
dependencies and the separate Apache-2.0 SDK 1.1.0 artifact are pinned; reviewed
community.proxmox `2.0.0` is installed offline from its digest-verified archive.
No dependencies install dynamically. Missing declared dependencies require a
runtime update. The CycloneDX inventory and upstream notices are included in
both release packages; final image/OS and native platform redistribution
qualification remains separate. The [I4A operator acceptance record](../architecture/integrations/i4a-completion-report.md)
confirms LIVE Docker/LXC acceptance is complete; native Debian/systemd LIVE
acceptance remains outstanding. Proxmox 9.2.11 remains unqualified and production
discovery, scheduling and complete snapshots remain disabled.

See [installation](installation.md), [upgrades](upgrades.md) and
[release verification](releases.md) for the supported operator workflows.
