# 0016 — Recover local maintenance, revocation evidence and bundled management

Status: **Accepted for Phase 4B.12A final recovery remediation**

Date: 2026-10-31

Supplements [ADR 0015](0015-local-release-execution-authority.md). Its execution,
approval, package trust, isolation and manual-only boundaries remain in force.

## Decision

Integrity-verified installed configuration metadata is available to existing
authorized scoped maintenance operations without an execution lease. Execution
continues to require the exact current lease. Repair cannot renew or issue one.

A revoked local activation may return to ordinary bundled management only through
an explicit root-reviewed signed handoff. It binds the original protected
instance/store/database and authenticated revoked artifact, exact active record,
dependent state, separate replacement store identity and production catalogue
package/evidence. An explicit replacement scope selection may adapt discovery
scopes to a probe-only package; original selections remain in signed evidence.
Configuration values, encrypted credentials and knowledge history are preserved.

The protected retained handoff and its PostgreSQL audit must agree. PostgreSQL
stores the signed pending handoff in a reserved internal SystemSetting; ordinary
application writes cannot alter it. The existing installation route still requires
global package-management permission, production catalogue authentication,
compatible healthy runtime inspection, settled runs, compatible dependencies and
normal taxonomy mappings. It consumes the handoff in the same transaction as
ordinary activation and completion audit. Rollback retains the handoff. Exact
active/dependent/store binding prevents replay. No local artifact is promoted or
given ordinary eligibility. Removing an override alone never performs restoration.

Revocation first durably publishes a protected denial-intent directory and fences
the current lease. API and runtime reject either that intent or a tombstone.
Complete signed evidence is written to a protected unique temporary file, flushed,
fsynced and atomically published without replacing existing evidence; the directory
is fsynced. Concurrent root operations retain the existing store lock.

Historical malformed tombstones require an explicit root recovery operation with
the reviewed corrupt-content digest. Exact bytes are retained as protected
forensic evidence before atomic replacement by a signed denial carrying their
digest/path. The denial intent remains throughout; recovery cannot restore
execution. Revocation and evidence-recovery audits reconcile idempotently after
database outages. No trust root or signature-verification policy changes.

## Limits

ADR 0015's filesystem, clock, root and database trust assumptions still apply.
The original binding, deployment identity and store mounts must remain available
through handoff consumption, using the same paths and physical identities.
Replacement-store relocation/recreation or changed build identity needs a newly
reviewed procedure; this handoff is not a cross-instance restore mechanism.
Already admitted jobs are not terminated. Live source and LXC acceptance remain
separate from the disposable recovery regressions.
