# IntegrationRuntime v1 specification

**I1/I2 implemented subset:** health, capabilities, verify_connector and
test_connection have a private authenticated client/server. Discovery/job/callback
operations below are I3 targets and remain unsupported. AnsibleRuntime is the
first adapter; domain requests have no playbook/inventory dependency. See
[contract ownership and AIP semantics](README.md).

## Operations and explicit types

| Operation | Request | Result |
| --- | --- | --- |
| health | no domain input | RuntimeHealth: state healthy/unavailable/incompatible, runtime version, approved baseline ID/digest, packaging mode, sanitised diagnostic code |
| capabilities | no domain input | RuntimeCapabilities: integration-runtime-v1, AIP versions, exact installed dependency/baseline versions and supported operations |
| verify_connector | VerifiedConnectorRef | RuntimeConnectorState: exact ID/version/digest verified in protected store or unavailable/incompatible; no store mutation |
| test_connection | TestRequest | ConnectionTestResult: success/failure, detected source version if available, Supported/Newer-untested/Known-incompatible, enabled-domain capabilities, missing capability/path codes, TLS/SSH trust state |
| start_discovery | DiscoveryRequest | RuntimeJobRef: opaque job ID, accepted timestamp and immutable request identity; duplicate request ID returns same job |
| get_job | opaque job ID bound to caller request | RuntimeJobStatus: queued/running/succeeded/failed/cancelled, timestamps, bounded progress/diagnostic codes; no secret/stdout payload |
| cancel_job | opaque job ID bound to caller request | idempotent cancellation receipt; terminal-state races resolved without losing evidence/cleanup |

`VerifiedConnectorRef` = stable Connector ID, exact SemVer, SHA-256 archive digest.
`TestRequest` = opaque request ID, verified reference, operation `test_connection`,
validated non-secret configuration, selected declared scopes, internal job-secret
lease reference and timeout. It has no ingestion token or evidence acceptance
because testing is not a discovery run. Source version/capabilities are returned
through the authenticated control response.

`DiscoveryRequest` adds persisted run/Integration IDs, echoed coverage key/mode/
domains, operation `discover`, run-scoped callback capability and resource bounds.
Atlas constructs callback location itself from trusted configuration; neither
Connector/browser chooses an arbitrary callback URL. Tokens and secret material
are sensitive control-transport data outside AIP and outside loggable request
representations. The API never accepts arbitrary command/path/playbook text,
source URL for executable code, uploaded archive or Galaxy identifier.

Both requests use an Atlas-issued idempotency ID bound to a request body hash.
Changed body at an existing ID conflicts. Runtime job ID is metadata, never
permission to operate another job. Runtime recomputes/checks the installed
ID/version/digest and approved entry selector immediately before each execution.
It cannot install/mutate its own protected store; only the approved privileged
Atlas installer can stage/activate code. `verify_connector` replaces the draft's
ambiguous `ensure_connector` installation wording.

## Transport and process authority

Control uses private HTTP with a generated high-entropy installation service
secret on **every** operation. It is independent of `AUTH_SECRET` and
`ATLAS_DATA_ENCRYPTION_KEY`. Constant-time credential comparison, bounded inputs,
redacted logging, protected secret files and deliberate rotation/restart overlap
must be implemented before I1 acceptance. Requests cannot treat loopback/private
addressing as authentication. Service-secret failure returns sanitized
unauthorized/unavailable states without disclosing expected values.

Docker exposes no host/public runtime port. API and runtime use the dedicated
`runtime_private` bridge with `internal: true` for authenticated control traffic.
Runtime also joins `runtime_source`, a dedicated non-internal bridge with normal
outbound routing to source infrastructure. No other Atlas service joins
`runtime_source`; PostgreSQL, Redis, gateway, web, worker and API retain their
existing networks. Source egress does not authorize control requests or create a
host/LAN runtime endpoint. Retain the read-only root filesystem, read-only
control/store mounts, dropped capabilities and `no-new-privileges`; do not use
host networking, privileged mode, `NET_ADMIN`, Docker socket or broad host mounts.

Native/systemd binds loopback and uses a pinned native Python/Ansible/Collection
environment; Docker/Podman is not required. Source stays in main Atlas repo,
packaging extends `infra/install`, `infra/docker`, `infra/systemd`, `infra/release`.
Normal installs include/enabled runtime; explicit manual-only opt-out remains.
Runtime failure cannot block viewing/editing existing Atlas knowledge.

Runtime has no Atlas user session, no general PostgreSQL access and no canonical
acceptance/tenancy authority. Atlas derives scope from persisted Integration/run.
Its worker owns schedule timing, overlap prevention, bounded retries and durable
run state. Runtime controls only bounded jobs, ephemeral workspaces, approved
source calls, normalization/validation, callbacks and cleanup. No new broker.

## Leases, completion and failure

Only declared required credential fields are leased internally for one test/job.
Use protected ephemeral material, `no_log` where relevant, redaction of events/
errors and final cleanup on success/failure/cancel/crash recovery. Runtime never
returns secret-bearing raw results. Credentials never appear in AIP.

AIP callback authentication is separate: short-lived audience/run/Integration/
Connector-bound token with JTI/expiry and revocation. Runtime may submit only
validated batches/completion for that run. Atlas verifies and seals them before
its lifecycle service decides absence. Control-job success without durable AIP
completion is insufficient for a complete snapshot. Callback failure/timeouts
produce a partial/failed Atlas run; no invented absence.

Use bounded request/job deadlines and sanitized diagnostic enums. Expired leases,
known-incompatible source/runtime, invalid mappings/configuration or changed
package digest fail before source execution. Cancellation revokes callback/lease
authority and cleanup is idempotent. Integration removal/disable must settle
in-flight work under Atlas ownership without causing absence.

## Acceptance by phase

I1 proves private health/control/verification, dedicated Docker source-egress
topology, default/manual-only packaging, protected store and safe independent
knowledge plane. Source reachability requires operator verification in the
deployment environment; network configuration alone is not live connectivity
evidence. I2 proves generic bounded Test Connection/leases without claiming live
vendor support before I4–I6.
I3 proves job dispatch, request replay, callbacks/finalisation/cancellation and
recovery with existing maintenance/quiescence. I4–I6 prove actual source calls;
I8 qualifies both deployment methods, failure injection and restore behaviour.

## Exact I2 transport

`POST /v1/connectors/test-connection` accepts exactly `reference` (Connector ID,
SemVer and unprefixed SHA-256 digest), UUID `request_id`, validated `config` and
internal `credentials`. The latter are source values transported only under the
independent runtime-control credential; this is not a browser API. Atlas owns the
lease and tenancy, and the runtime accepts neither scope nor callback authority.
The fixed verified entry is `test_connection.yml`; callers cannot select paths,
commands, repositories, arguments or playbook text. Requests are limited to
128 KiB, results to 4 KiB, concurrent probes to four and execution to 22 seconds.
API probe transport has a 28-second deadline; health remains three seconds.

Result fields are bounded enums/booleans and a sanitized source-version string.
Atlas classifies it using the exact installed Manifest: qualified exact versions
are supported, known-incompatible versions blocked and unqualified/newer results
untested. Test Connection writes safe audit/last-test metadata only. It creates
no DiscoveryRun, evidence, AIP receipt, Asset, Service or Business Function.
