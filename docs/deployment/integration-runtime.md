# Local integration runtime and Connector catalogue

Normal Docker Compose and native/systemd installations include an isolated Atlas
Ansible Runtime. Open **Integrations → Catalogue** to inspect the bundled offline
catalogue, or **Runtime** with a global runtime-view grant to inspect health,
versions and the approved dependency baseline. The browser calls Atlas API;
it never connects directly to the runtime.

The current Proxmox VE, Docker + Compose and UniFi Network entries are verified
catalogue metadata. Their executable bundles are not released or qualified yet.
There is no Configure, Test Connection, Run Now or source-credential flow in this
shell. Package installation actions appear only when an approved verified release
bundle and a compatible runtime actually exist. Arbitrary archive uploads,
download URLs, Git repositories, playbooks and Galaxy installs are not supported.

## Deployment and authentication

Docker attaches `runtime` to two dedicated bridge networks:

- `runtime_private` has `internal: true` and carries authenticated API-to-runtime
  control traffic. Only API and runtime join this network.
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

The runtime receives no PostgreSQL, Redis, user/session or source-system
credentials. A networkless one-shot provisioner creates a random 384-bit control
credential in the durable `runtime_control` volume. API and runtime mount that
volume read-only. Existing valid material is preserved and invalid existing
material is refused.

Native installs create a separate `/opt/atlas/runtime-venv` with pinned Python
dependencies, and `atlas-runtime.service` under the dedicated `atlas-runtime`
account. The listener is fixed to `127.0.0.1:8091`; Docker or Podman is not required.
The separate control credential is `/etc/atlas-runtime/control.secret`, owned by
root, group `atlas-runtime-control`, mode `0640`, inside a `0750` directory. API
and runtime have that supplementary reader group. The runtime never receives
`/etc/atlas/atlas.env` or database authentication material.

Every health, capability and package-inspection request authenticates with this
independent control credential. It is never shown by normal UI/API responses or
logs. Protect and retain it across upgrade/reinstall; neither installer silently
rotates an existing valid value. Source credentials and later run-scoped callback
credentials have separate ownership and are not implemented here.

## Failure and manual-only operation

Runtime requests have a three-second total timeout and bounded response parsing.
An outage produces **Unavailable**; a changed protocol/dependency baseline produces
**Incompatible**. Accepted Atlas knowledge remains usable in either state.
Runtime startup/readiness failures are reported without preventing core API/web
installation health and setup hand-off. The runtime does not execute discovery
jobs in this shell.

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
runtime to apply network membership while preserving the running API, control
credential and Connector store. A container restart alone does not apply the
network change.

```bash
atlas_compose() {
  docker compose --env-file .env -f infra/docker/docker-compose.yml "$@"
}
atlas_compose config --quiet
atlas_compose build runtime
atlas_compose up -d --no-deps --force-recreate --wait --wait-timeout 60 runtime

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
with API and runtime; the source network must report `internal=false` with only
runtime. Check **Integrations → Runtime** is healthy after recreation. The socket
probe proves outbound TCP reachability only; it uses no source credentials and
does not test TLS, Proxmox authentication or discovery. Record live connectivity
as passed only after this probe succeeds in the operator's deployment. If it
still fails, investigate the LXC/host route and firewall using the exact error.

## Protected packages and compatibility

Catalogue content is release-packaged JSON; PostgreSQL records only the active
installed identity and safe verification/baseline metadata. Packages are global,
with one active version per Connector. `integration_runtime.manage` must be held
globally; scoped `integrations.manage` never authorizes executable installation.
All live configured connections, including disabled connections, block removal.
Package removal never deletes Assets, runs, assertions, evidence or Changes.

The store is `/var/lib/atlas-connectors`. Native ownership is root with runtime
read-only access; its future executable release install path must retain the
privileged operator/package boundary. Docker exposes a writable store only to
trusted Atlas package-management code; the runtime's mount is read-only.
Exact identity, SHA-256, approved bootstrap allowlist/provenance, Manifest schema,
embedded metadata and bounded plain USTAR contents are checked before atomic
publication. The runtime independently checks the archive and extracted hashes.
Uninstall first quarantines all versions of the Connector and removes database
authority atomically, then completes file cleanup; rollback restores the address
if the transaction fails. Prior inactive immutable versions support explicit
catalogue-driven rollback while installed; uninstall removes their code too.
No automatic version activation occurs.

Official remote installation is disabled and fails closed while the reviewed
GitHub/Sigstore verifier, pinned trust roots and official release workflow are
unavailable. There is no skip-verification switch. Bundled packages, when qualified
and shipped later, require exact digests bound to the trusted Atlas release.
The current offline catalogue needs no Internet connection and ships no executable
vendor bundles.

The approved environment identifies runtime `0.1.0`, protocol
`integration-runtime-v1`, baseline `atlas-ansible-i1-v1` version `1.0.0`,
ansible-core `2.19.7` and ansible-runner `2.4.3`. All fourteen Python dependencies
are pinned; no vendor Collections are prequalified and no dependencies install
dynamically. Missing declared dependencies require a runtime update. The initial
CycloneDX inventory and upstream notices are included in both release packages;
final image/OS and native platform redistribution qualification remains separate.

See [installation](installation.md), [upgrades](upgrades.md) and
[release verification](releases.md) for the supported operator workflows.
