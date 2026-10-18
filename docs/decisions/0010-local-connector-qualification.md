# 0010 — Exact local operator authorization for Connector qualification

Status: **Accepted for I4C-A preparation (explicit operator task, 13 October 2026)**

## Context

[ADR 0006](0006-verified-connector-supply-chain.md) permits verified official
immutable packages; normal activation rejects unqualified discovery packages.
The I4B fixture harness changes identity/qualification and cannot qualify the
unchanged candidate against a real source. Remote Sigstore verification remains
unavailable. The operator explicitly requested a contained generic qualification
path, with no production catalogue, bootstrap, release or qualification changes.

## Decision

Add a local installation-authority CLI, with explicit isolated-instance
acknowledgement. API, worker and runtime must opt in through local process
configuration and use a separate protected store. The normal store is excluded.
An immutable 48-hour authorization binds one prerelease ID/version/archive digest,
the entire detached manifest digest, both source commits and the store path.
It accepts only an unqualified candidate with no qualified source versions.

The existing package installer performs bounded archive, manifest, licence,
digest and per-file verification. Evidence is explicitly `operator-qualification`,
never an official release attestation. API and runtime independently enforce
permission, expiry, exact identity, receipt binding and protected file access.
Removing permission or opt-in fails closed for subsequent execution.

Only the local CLI can activate this package in the isolated test database. It
reuses the global one-active-version lifecycle, mapping resolution, dependent
configuration checks, healthy exact runtime compatibility, run locks and audit.
Existing generic connections must use manual scheduling. Normal catalogue APIs
gain no input, upload, install source, authorization switch or qualification rule.
Normal scoped Test Connection and Run Now still enforce their existing RBAC.

This is a limited additive exception to ADR 0006's package authority; its
production trust model and [ADR 0007](0007-global-connector-scoped-integration.md)
remain in force. No accepted historical ADR is rewritten or superseded.

## Consequences and validation

The grant authorizes testing; it never qualifies a source/version or promotes a
candidate. The operator must review/push both source commits, reconstruct the
candidate and verify its recorded digest before staging. A digest establishes
byte identity; local operator approval establishes this test-only authority.
There is no GitHub attestation claim or download fallback.

An isolated qualification instance has one active candidate version locally;
ordinary instances keep their shipped probe-only catalogue. The supported Docker
override retains runtime read-only store mounts and contains no secrets. Cleanup
revokes permission, settles jobs and restores the ordinary store/configuration;
history is retained. Live acceptance is a separate operator gate.

See [operator procedure](../deployment/connector-qualification.md) and
[preparation evidence](../architecture/integrations/i4c-a-preparation.md).
