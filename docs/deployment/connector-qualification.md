# Local Connector qualification checkpoint

This is an explicit operator procedure for an **isolated Atlas test instance**.
It does not publish, qualify or promote a Connector. Normal catalogue installation
continues to reject unqualified discovery packages. Read
[ADR 0010](../decisions/0010-local-connector-qualification.md) before using it.
The Proxmox-specific live checklist belongs in atlas-connectors at
`connectors/proxmox/docs/i4c-live-qualification.md`.

## Authority and prerequisites

Use the exact reviewed/pushed Atlas and Connector commits with clean checkouts.
Build the candidate using its canonical builder; independently verify the expected
digest and committed-source identity before bringing files to Atlas. The operator
approves these local bytes; there is **no GitHub/Sigstore attestation claim**.
The CLI checks the exact detached manifest, archive digest, Connector source commit
and Atlas `ATLAS_BUILD_ID`. No download, arbitrary playbook or credential argument
exists. The SDK and AIP are unchanged.

Only root (native) or the existing Compose installer UID/GID 10001 can invoke the
command. An explicit `--ack-isolated-test-instance` is required. API, worker and
runtime must each have `ATLAS_CONNECTOR_QUALIFICATION_ENABLED=1` and the same
separate absolute `ATLAS_CONNECTOR_STORE_PATH`.
API/worker/runtime must also report the exact same public `ATLAS_BUILD_ID` as the
grant's Atlas commit; a changed build identity revokes its applicability. The normal
`/var/lib/atlas-connectors` path is prohibited. Do not set opt-in on a production
instance or share the qualification database/store with one.

There is one active version per Connector **in the test instance**. Existing
generic connections/credentials/DataSources can be retained; all dependent live
connections must be manual, with no pending/running/unsettled discovery jobs.
Legacy plugin connections are rejected. Back up the test database using the
existing Atlas backup workflow before changing its local active package.
The CLI never accepts source token values.

## Docker/LXC procedure

Use the same checkout, environment file, project name and established overrides
as the test deployment. Append `infra/docker/docker-compose.qualification.yml`
last. The following example assumes the existing default project and `.env`;
adapt only those deployment selectors after inspecting the running deployment.
Each command is a separate operator checkpoint.

1. Verify the checkout is clean and at the approved commit. Set its public build
   identity; this contains no credential:

   ```bash
   git status --short
   git rev-parse HEAD
   export ATLAS_BUILD_ID="$(git rev-parse HEAD)"
   ```

2. Define the exact Compose invocation and build the changed processes:

   ```bash
   dcq=(docker compose --env-file .env -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.qualification.yml)
   "${dcq[@]}" build api worker runtime runtime-init connector-bootstrap
   ```

3. Provision the separate volume and retain the existing control credential:

   ```bash
   "${dcq[@]}" run --rm --no-deps runtime-init
   "${dcq[@]}" up -d api worker runtime
   "${dcq[@]}" ps
   ```

   The normal `connector-bootstrap` prerequisite still stages only the original
   production packages into the original store. The override creates a distinct
   qualification volume, API writable and worker/runtime read-only. Existing
   secret volumes, source network, fixed entry points and isolation stay intact.
   Inspect **Integrations → Runtime** and require healthy baseline identity.
   Do not print `docker compose config` or environment files containing secrets.

4. Copy only the previously verified bundle and its detached manifest into the
   API container's temporary input directory. `CANDIDATE_DIR` must point to the
   clean committed-source build on the LXC:

   ```bash
   "${dcq[@]}" exec -T api mkdir -p /tmp/qualification-input
   "${dcq[@]}" cp "$CANDIDATE_DIR/manifest.json" api:/tmp/qualification-input/manifest.json
   "${dcq[@]}" cp "$CANDIDATE_DIR/$CANDIDATE_FILE" api:/tmp/qualification-input/candidate.tar.gz
   "${dcq[@]}" exec -T --user 0:0 api chmod 0444 /tmp/qualification-input/manifest.json /tmp/qualification-input/candidate.tar.gz
   ```

   This copies inputs to temporary storage, never executable files into the
   protected Connector store. The installer independently rehashes/extracts them.

5. Define the reviewed public checkpoint arguments from the Connector runbook:

   ```bash
   checkpoint=(--ack-isolated-test-instance --manifest /tmp/qualification-input/manifest.json --bundle /tmp/qualification-input/candidate.tar.gz --connector-id "$CONNECTOR_ID" --version "$CANDIDATE_VERSION" --digest "$CANDIDATE_DIGEST" --atlas-commit "$ATLAS_BUILD_ID" --connector-commit "$CONNECTOR_COMMIT")
   "${dcq[@]}" exec -T --user 10001:10001 api python -m scripts.qualify_connector stage "${checkpoint[@]}"
   ```

   Use the explicit installer UID/GID even if the API image account has a different
   primary group. This preserves the existing bootstrap installation authority.
   Temporary inputs contain no credentials; the preceding mode change only makes
   those digest-verified inputs readable by the installer.

   Staging changes no database activation. It writes a protected 48-hour grant
   for one exact tuple/manifest/store and the ordinary immutable package layout.
   The receipt's authority is `operator-qualification`. Grant recreation requires
   explicit revoke and restaging; idempotent staging never silently renews expiry.

6. Preview candidate requirements without persisting database changes:

   ```bash
   "${dcq[@]}" exec -T --user 10001:10001 api python -m scripts.qualify_connector plan "${checkpoint[@]}"
   ```

   Review unresolved required mappings and dependent configuration. Normal
   mapping APIs remain catalogue-based and cannot configure this unlisted version.
   If required, create/review managed reference records in Atlas's normal
   Administration UI; do not hard-code or silently redefine taxonomy semantics.
   Supply a local JSON list with explicit choices, for example the source-neutral
   shape `[{"kind":"asset","source_key":"vendor.node","target_key":"hypervisor_node"}]`.
   Only declared Asset/Relationship classes and existing active targets are
   accepted. Required/optional ignore shortcuts are not provided. Existing
   relationship direction and endpoint-type compatibility remain enforced.

   Copy the reviewed file to `/tmp/qualification-input/mappings.json`, make this
   non-secret input readable with `exec -T --user 0:0 api chmod 0444 /tmp/qualification-input/mappings.json`, then
   preview with `--mappings /tmp/qualification-input/mappings.json` and repeated
   `--scope <declared-scope-key>` as needed. The preview reports mapping resolution
   and configuration readiness and rolls back all changes. Scope selection applies
   explicitly to **every dependent live test connection**; inspect their count.
   Correct TLS/configuration through the existing Integration UI before activation.
   Never clear/replace saved credentials merely to stage a package.

7. After a ready preview, run `activate` with the **same reviewed mapping/scope
   arguments**. It rechecks healthy compatible runtime and independent runtime
   package verification before committing the local active version. Existing
   mapping resolution, dependent configuration, run locks and audit are used.
   Previous active identity remains authoritative if activation fails.
   Activation itself makes **no source call** and performs no discovery.

8. Inspect **Integrations → Runtime** / installed package identity and the saved
   connection. Test Connection and Run Now use their existing scoped permissions,
   encrypted secret provider, worker, Runner, AIP and reconciliation. Follow the
   Connector-specific live checklist interactively; leave scheduling manual.

## Revocation and recovery

Disable the test connection and cancel/settle any pending/running jobs through
the normal UI. Revocation blocks **new** verification/execution; it does not kill
jobs that were already authorized. Then revoke explicitly:

```bash
"${dcq[@]}" exec -T --user 10001:10001 api python -m scripts.qualify_connector revoke --ack-isolated-test-instance
```

Retain run/evidence history and record the checkpoint. Recreate API/worker/runtime
with the original Compose selectors **without** the qualification override.
The original store and bootstrap bytes have been preserved. Use the existing
global-admin package path only after its dependent configuration is compatible.
For example, candidate `inventory` scopes are undeclared by the original probe-only
package, so its existing activation guard rejects that configuration. This slice
does not provide automatic conversion or a one-click previous-version restore.
Retain the disabled qualification connection/database/history for a separately
reviewed compatible restore; removing the override with a candidate active row
keeps that connection unavailable rather than executing unapproved bytes. Do not
remove Integrations or destroy the database/volumes to roll back. Do not leave
candidate schedules enabled. Expired or revoked packages remain non-executable
even when their historical active row is retained.

## Native boundary

The same CLI can run under root with the test API's private environment and a
separate root-owned store. API/worker/runtime require explicit opt-in and matching
store paths in their protected systemd configuration. Retain runtime read-only
access, reader groups, control credential, fixed listener and isolated dependency
environment. Never source API/database environment into the runtime. Native
Debian/systemd **LIVE acceptance remains outstanding**; Docker/LXC is the selected
I4C-A handoff path. Do not claim native acceptance from local Python tests.
