# Discovery diagnostics v1

Diagnostics extend private runtime control, separately from AIP 1.0 and SDK 1.1.0.
Atlas remains vendor neutral. Accepted knowledge, reconciliation, source scope,
privileges and COMPLETE/PARTIAL policies are unchanged.

## Execution and trust boundaries

The runtime creates `diagnostics.ndjson`, mode 0600, in its existing private 0700
workspace and retains its descriptor/inode. Only fixed discovery execution receives
that destination. No control request accepts a diagnostic path, command, environment
or callback URL. The Connector appends unbuffered JSON lines as work proceeds.
Normal diagnostics are always enabled; debug adds allowlisted metadata only.

After stopping descendants, the runtime parses a bounded validated prefix on
success, PARTIAL, failure, exception, timeout and cancellation. It checks regular
file type, owner, mode, link count, inode identity, sequence, schema and known
source/control/ingestion credentials. Replaced paths, links, malformed events,
partial lines and overflow produce safe processing reasons. Offending bytes are
discarded. Nonempty traces without `discovery_finished` are incomplete. Empty
sidecars preserve older Connector compatibility and are reported unavailable.
Workspaces and credentials are still removed on terminal paths.

The sanitized report travels through authenticated terminal job status. The API
independently validates it before persistence. Diagnostic processing errors block
successful completion callbacks; diagnostic warnings/errors also block a
contradictory COMPLETE seal. Existing AIP/absence gates remain authoritative.
Debug off/on preserves observations, relationships, source calls, warnings and
completeness. Diagnostics do not repair or relax source validators.

This uses the existing workspace/control transport instead of changing AIP/SDK.
It extends ADR 0003 within its runtime/application boundaries, without superseding
an accepted decision. Source-child/Ansible failure and bounded termination retain
flushed evidence. Abrupt loss of the entire runtime service can still lose a
transient control result before Atlas receives it, as with existing ephemeral jobs.

## Schema and bounds

Required fields: `sequence`, `stage`, `result`, `reason_code`. Result is accepted,
skipped, warning or error. Optional normal fields: `object_class`, `external_id`,
`parent_external_id`, `source_category`, `record_count`. Tokens match
`[a-z][a-z0-9_.-]{0,63}`; external identities match
`[A-Za-z0-9][A-Za-z0-9_./:-]{0,191}`. No free text field exists.

Debug adds only `field`, `encountered_type`, `validation_rule`, `expected`, `action`,
using bounded tokens. Type is null/boolean/integer/number/string/array/object/unknown.
Actual values, body/config serialization, comments, descriptions, URLs/queries,
headers, commands, environment and mount contents are excluded. Known credentials
and credential markers are rejected again by runtime validation.

Limits: **8,192 events**, **768 bytes per encoded line**, **6 MiB total sidecar**,
**128 permanent warning/error contexts**. Counts/reason totals cover the validated
stream even when contexts are truncated. The writer applies the same worst-case
event-size budget in both modes. Overflow emits `diagnostic_limit` and fails closed
before successful completion/absence processing.

Processed/accepted/skipped counts describe classified inventory rows and guest
interface subrecords through `record_count`. They differ from AIP observation
counts: one row can produce several entities/relationships. Warning/error totals
also include source-read and cross-record checks that consume no row. Stages and
reason/context explain a compatible outward warning such as `invalid_source_record`.
Accepted here means accepted by normalization; it never means automatic acceptance
of canonical Atlas knowledge or reconciliation items.

## Persistence, RBAC and retention

Migration `20261018_0030` adds Integration `debug_next_run`, immutable run
`debug_enabled`/`debug_expires_at`, permanent `diagnostics_summary`/`diagnostics_events`,
and separate `discovery_run_debug_traces`. A trigger freezes debug intent and binds
it to execution provenance. Ordinary run APIs expose normal diagnostics and the
immutable enabled flag, with no debug trace.

Arming requires global `integration_runtime.manage` plus scoped `integrations.view`.
It defaults off. Existing Integration locks/active-run guards serialize all triggers.
Insertion copies the flag into the run and clears the Integration in one transaction.
Rollback preserves arming; failure after creation never rearms it. Debug GET/DELETE
independently require global management plus the same scoped view. GET is no-store.

Expiry is fixed at creation plus **48 hours**, with immediate unavailability after
expiry. The existing five-second worker tick physically deletes expired rows;
reads purge expired rows too, and worker restart resumes cleanup. Explicit deletion
removes debug rows, records audit/deletion metadata, prevents later reconciliation
from rehydrating them, and requests removal from the runtime's transient result.
The runtime server prunes terminal jobs after 30 minutes even without new runs.
Portable backups exclude debug table data, retaining normal provenance and intent.

No new queue, scheduler, daemon, raw-source endpoint or vendor frontend parser is
introduced. Source credentials remain private leased inputs. No physical memory
or PostgreSQL WAL zeroization guarantee is made.
