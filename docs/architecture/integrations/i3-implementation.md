# I3 orchestration and AIP implementation

I3 extends the existing Integration, worker, DiscoveryRun and knowledge lifecycle.
The canonical SDK remains 1.1.0; Manifest discovery capability is `read_only`
(or `false`), and AIP remains 1.0. Official Proxmox 0.1.0 remains probe-only.
No production discovery Connector is shipped. See the [completion record](i3-completion-report.md)
for actual validation and deployment acceptance limits.

## Durable intent and execution

PostgreSQL owns fixed schedule intent and run state. Run creation snapshots the
verified Connector tuple, Manifest/AIP/SDK identity, runtime baseline and lock
digests, selected scopes, exact global mappings, non-secret configuration and
credential revision. A database trigger freezes provenance, scope and coverage;
the Integration/source context is checked at insertion. A partial unique index
also protects executable ownership until terminal cleanup settles. Legacy runs
retain their existing fields and behavior.

API and scheduler serialize through the existing Connector advisory lock and
Integration row lock. Redis carries bounded disposable dispatch hints; each
worker also scans durable pending/recovery intent. Queue loss cannot lose history.
Pending dispatch expires after 15 minutes. Runtime availability/capacity retries
use three attempts with exponential delay; deterministic configuration/source
errors pause scheduling until corrected. Missed schedule ticks coalesce into one
current run. Manual, hourly, 6-hour, 12-hour, daily and weekly presets are supported.
Authorized creation schedules an immediate onboarding run and hourly default when
the Manifest supports scheduling; manage permission alone cannot authorize it.

Dispatch verifies the frozen tuple/configuration/revision again, materializes only
declared visible secret fields, mints a run token, commits its generation before
callbacks, and submits private runtime control. The runtime request ID is the
Atlas run ID. Ambiguous starts are queried by that identity, never blindly retried.
A 15-second start grace avoids another worker misclassifying an in-flight start.
Runtime disappearance, deadlines and success without a valid completion fail the
run without evaluating absence. Cancellation revokes ingestion immediately;
runtime cleanup remains bounded and retains executable ownership until settled.

## Narrow ingestion authority

API startup atomically provisions `discovery-ingestion.secret` in installation
state, mode 0600. Only API and worker need access. It is independent of session,
runtime-control and data-encryption secrets, and survives restart/upgrade.
HS256 tokens have fixed issuer/audience `atlas-integration-ingest`, one run and
Integration, issued-at/expiry and a generation UUID. Dispatch normally uses an
11-minute lifetime; the service refuses lifetimes above 15 minutes. Tokens never
persist in PostgreSQL. Normal user authentication never accepts them.

Ingestion loads persisted run/Integration/DataSource ownership rather than taking
tenancy from claims or payload. Disable, retirement, credential/configuration
change, cancellation or failed orchestration revoke active authority. Terminal
seals permit only acknowledgment of an identical completion hash until expiry;
they grant no batch or domain-write authority. This narrow acknowledgment handles
a lost completion response without reopening a finalized run. Conflicting seals
fail closed. Restore invalidates every persisted token generation and fails active
runs; destination-local signing state stays outside the database backup.

## Canonical receipts and lifecycle adapter

Canonical SDK validation checks schema and declared class/fact semantics. Atlas
adds frozen tuple/coverage binding, exact active mapping checks, scoped endpoint
references, selected classes and decoded credential/JWT/private-key rejection.
Limits are 1 MiB per body, 256 batches, 5,000 observations, 20,000 facts and
32 MiB canonical JSON per run; the SDK's smaller field limits also apply.

Immutable receipts use canonical `(run_id, batch.sequence)` and canonical body
hash. Identical replay acknowledges the receipt; conflicting content fails the
run. Batches may arrive out of order, but completion requires every sequence from
1 through `last_sequence`. Evidence and RunObservedEntity membership are written
atomically with each receipt. No source-current/reconciliation changes occur until
successful finalization. Failed/cancelled runs retain valid immutable evidence.

Successful finalization translates into the shared `ingest_observations`,
`record_assertion`, `create_item`, entity-resolution and Changes services.
Network/Interface observations extend those same review services and gain scoped
source links. Explicit technical identity linking preserves manually accepted
configuration and creates a separate configuration review. Connector identity
resolution uses its own durable link; matching manual/other-source entities require
an explicit link decision. Relationship direction is translated from the declared
semantic direction into Atlas's mapped type rules.

Namespaced facts retain value type, class and cardinality metadata. A multi-fact
is one atomic value-set assertion containing the canonical list; it does not
reinterpret Atlas's existing predicate rollup as independently accepted list
members. Fact classification never grants automatic acceptance or writes arbitrary
Asset columns. Existing acceptance/source-current/history policy is retained.

Only successful full coverage with explicit complete status and no incompleteness
diagnostic calls the existing `reconcile_complete_snapshot`. Asset-only absence
and re-observation semantics remain unchanged; no Network/Interface absence or
automatic deletion is introduced. Partial, failed, cancelled, interrupted and
unsealed runs never call absence evaluation.

## Replaceable runtime and deployment

The private runtime supports start/status/cancel with exact verified package
identity and fixed `discover.yml`. It accepts no executable path, command, Git,
Galaxy or callback URL. Four discovery jobs run concurrently, each bounded to
10 minutes; the registry retains only safe job metadata and request hashes.
Private 0700 workspaces and 0600 files carry leased inputs, never argv/environment.
The Connector receives no ingestion, control, user-session or database credential.
It emits canonical NDJSON privately; the parent sends fixed Atlas callbacks in a
separate bounded transport child. Redirects and ambient proxies are disabled.

Ansible workers can create independent sessions. Cancellation/deadline freezes
and collects the bounded descendant tree with pinned psutil before killing its
root and groups; process identity checks avoid targeting another job. The fixed
subprocess Runner also avoids pexpect's extra session. Docker's init reaps orphaned
descendants. Workspaces are deleted on every terminal path and owned remnants are
cleaned at startup. Output/events are suppressed. Access revocation and cleanup
are guaranteed; physical memory zeroization is not claimed.

Docker adds worker membership in `runtime_private`, read-only control/state/store
mounts and the existing data key for SecretProvider materialization. API provisions
the signing key before healthy startup; worker waits for API health. Only runtime
joins `runtime_source`; gateway remains the sole public ingress. Runtime has no
DB/auth credentials, store write access, Docker socket or host root mount.

Native worker uses a filtered root-owned environment and control-reader group;
the existing shared Atlas UID remains for API/worker maintenance locks. The web
unit masks installation state. This reduces service exposure but does not claim
complete host-user separation from the pre-existing shared Atlas account.
The runtime has its own account/environment and fixed loopback listener/callback.
Both methods bound runtime memory/tasks. Actual Docker/LXC build/deployment,
migration, retained I2 probes, signing-state restart preservation and inspected
isolation/hardening are operator-confirmed in the [completion report](i3-completion-report.md).
Native Debian/systemd LIVE acceptance has not been performed and remains outstanding.

Restore refuses replacement while the destination has unsettled generic runs.
Cancel those runs and wait for cleanup first. Imported active runs fail as
`restore_interrupted`; all imported generations are revoked before maintenance
ends. This preserves the existing restore/quiescence boundary without leaving
untracked source execution behind a replaced database.
