# Integration discovery runs

I3 provides generic orchestration and ingestion. Official Proxmox 0.1.0 supports
Test Connection only; its detail page explains that inventory discovery is
unavailable and exposes no Run Now or schedule control. No production discovery
Connector is shipped. Deterministic executable fixtures are test infrastructure,
excluded from the catalogue, bootstrap and release packages.

For a future qualified discovery-capable package, configure its authorized
Customer/Site, credentials and declared scopes. Global administrators resolve
required taxonomy mappings first. A user needs scoped `integrations.run` to run
discovery; configuring or managing the connection does not replace that grant.
Enabled configured versions expose **Run Now**, current run, last run/success,
next run, safe latest error and history. Successful authorized creation queues an
initial run and chooses hourly scheduling only when the Manifest permits it.

## Schedules and overlap

Schedule changes require both scoped manage and run permission. Choose Manual,
Hourly, Every 6 hours, Every 12 hours, Daily or Weekly. Custom cron expressions are
unsupported. Missed intervals coalesce into one run; the worker does not replay a
backlog after an outage. An Integration has one active executable owner, including
terminal runs awaiting runtime cleanup. A racing manual/scheduled request returns
the existing run identity. Different Integrations can use the four runtime slots.

Disable, retirement, changed configuration/scopes or credential replacement/clear
cancels active intent and revokes ingestion. Credentials remain write-only. A
running job may take a short bounded cleanup interval before another run is
eligible. **Cancel run** records cancellation promptly; worker/runtime stop and
reap source children separately. Cancelling never evaluates absence.

## History and review

Use the existing **Discovery** page or **Run history** on the Integration. List
and detail show authorized run state, Connector/version, trigger, scope, batches,
observations, warning count, timestamps and safe error. Detail adds duration,
source version, reconciliation summary and runtime/baseline identity. Opaque job
and digest metadata are available in Technical identity. Credentials, tokens,
private paths and Ansible output are not returned.

Valid batches create immutable source evidence and run membership. Successful
finalization creates source-current assertions and review items through Atlas's
existing lifecycle. Failed/cancelled execution retains valid evidence and accepted
knowledge. Review discovered Assets, Networks, Interfaces, source facts and
relationships through existing reconciliation APIs/UI; accept/link owner Assets
and Networks before dependent Interfaces. Matching a manual Asset requires an
explicit source link decision. Namespaced source facts never write arbitrary
Asset fields or infer Services, Business Functions or business recovery metadata.

For a Network or Interface already entered manually, the scoped
`POST /api/reconciliation-items/{item_id}/link-technical` endpoint takes
`entity_id` and optional `reason`. It requires reconciliation decision and
`networks.edit` permissions in the same Customer/Site. Interface ownership must
resolve to the same accepted Asset. Linking preserves manual configuration and
creates a separate configuration review. The new source association picker is
API-only; the normal accept/reject/defer review remains in the existing UI.

Only explicitly successful, complete full coverage with a matching prior baseline
can create Asset no-longer-observed review items. Partial, failed, cancelled,
timed-out, interrupted or unsealed runs never infer absence. No Asset is deleted
automatically, and re-observation preserves history. Network/Interface absence
remains outside the existing Asset lifecycle.

## Recovery and deployment

PostgreSQL retains runs, receipts and schedule intent. Redis is a disposable hint
queue; loss of Redis does not lose intent/history. Worker restart scans pending
runs and queries existing runtime jobs by run identity. Runtime restart makes
interrupted jobs fail safely; it cleans owned abandoned private workspaces.
Success without an accepted completion fails as missing completion. Pending
dispatch expires after 15 minutes; transient availability/capacity uses at most
three attempts. Fix deterministic configuration/authentication/compatibility
errors before scheduled execution resumes. A manual retry creates a new run.

Use **Integrations → Runtime**, service status and safe run IDs/error categories
for diagnosis. Docker logs may be inspected with `docker compose logs worker runtime api`
using the supported protected configuration. Native equivalents are
`journalctl -u atlas-worker -u atlas-runtime -u atlas-api`. Never include source
credentials, Authorization headers or raw private input files in support material.

Cancel destination active runs and wait for runtime cleanup before restoring a
database. Restore revokes imported token generations and fails restored active
runs. The separate installation-local signing file is retained across normal
upgrade/restart and excluded from database backups. See [backup/restore](backup-restore.md)
and [runtime deployment](integration-runtime.md).

Local acceptance uses real PostgreSQL/Redis, real Ansible children/private HTTP
callbacks and the production browser build with intercepted deterministic API
state. Actual I3 Docker/LXC build/deployment, migration, retained I2 probes,
signing-state restart preservation and inspected isolation/hardening are
operator-confirmed. Native Debian/systemd LIVE acceptance has not been performed
and remains outstanding. Proxmox inventory discovery, 9.2.11 qualification and
remote GitHub/Sigstore qualification remain future boundaries. See [validation](../architecture/integrations/i3-completion-report.md).
