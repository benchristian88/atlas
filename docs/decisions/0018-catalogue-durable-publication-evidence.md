# 0018 — Durable original publication evidence and remote installation

Status: **Accepted — architectural contract only; activation approvals outstanding**

Proposed: 2026-11-04

Accepted: **2026-11-05 (Pacific/Auckland)**, by explicit project-owner instruction,
subject to preserving future native/systemd installation compatibility.

## Decision scope

This accepts the seven-asset, historical-authorization, selection-binding,
disabled-recovery and separate installation-authority decisions below, including
their assurance limits. It supplements the future-publication proposal in
[ADR 0012](0012-official-catalogue-publication-authorization.md); that ADR remains
**Proposed** as a whole. Its historical evidence is unchanged. This is a narrower,
explicit decision, not blanket acceptance of its options or recovery proposals.

This refines [ADR 0006](0006-verified-connector-supply-chain.md)'s protected
execution boundary and [ADR 0011](0011-offline-official-provenance.md)'s independent
offline verifier policy for the explicitly reviewed reusable preflight signer.
It preserves [ADR 0013](0013-sequence-one-consumer-bootstrap-approval.md)'s exact
sequence-one exception and [ADR 0015](0015-local-release-execution-authority.md)/
[ADR 0016](0016-local-release-recovery.md)'s local authority, PostgreSQL activation,
lease, revocation and handoff requirements. None is superseded.

Architectural approval does **not** approve a successor SHA, policy fingerprint,
new executable trust pins, release/run identities, publication gate, workflow
adoption, remote installation policy or deployment. All corresponding Catalogue 2
approval records remain unset. No live signing, publication, installation or
native acceptance is established by this decision.

## Publication evidence

Future ordinary sequences carry exactly seven immutable assets: numbered
catalogue, catalogue bundle, original current pointer/bundle, original v2
preflight/bundle and exact source policy. Authenticate original bytes with
Atlas's independently pinned verifier/roots, successor signer S, exact policy
digest, numeric identities, original source C and first-attempt run. A release
archive, producer policy, receipt, environment or request cannot select Atlas
authority. The pure signed-observation validators are Atlas-owned copies of
the existing producer contract, with no administrative transport or credentials.

## Historical authorization

Require original signed observation ordering and at most 900 seconds from
observation start through expiry. Require all verified preflight transparency
times within issuance/expiry, original run creation before observations, all
selection witnesses after preflight witnesses, selection within **900 seconds**
of original signed issuance and publication within **300 seconds** of the latest
authenticated selection witness. Supported Tlog witnesses come from the existing
pinned roots and two allowlisted log URIs; one through eight verified witnesses
are accepted, not a two-log quorum. These exact limits and witness semantics are
accepted. Historical evaluation never admits an expired live job or proves
continuous protections. GitHub `published_at` remains transport metadata, not a
signed time. Independently retrieve and validate original run/attempt timing and
actual publication time; unavailable, contradictory or inconsistent time evidence
rejects. Unsigned GitHub timestamps cannot supply cryptographic time witnesses.
Preserve the thirty-second pre-finalization reserve and authoritative
post-publication checks described below; the reserve extends no accepted bound.

## Selection binding

Accept implementation-enforced correlation: original preflight and
independently signed selection have identical C/run/attempt; build signature
and release tag agree on C; retained selection/bundle are byte-identical in
that immutable seven-asset release; and the reviewed publisher enforces one
selection per source. The consumer also rejects source reuse within its chain.
The preflight does **not** directly sign a later pointer or numeric asset IDs.
This reliance on reviewed implementation/co-location is explicitly accepted.
The successor implementation and genuine signing evidence still need separate review.

## Recovery

Keep cross-job production recovery **disabled pending a permanent recovery-archive
decision**. The unchanged executable disposition is
`disabled-pending-permanent-archive-decision`. The inherited recovery evaluator
verifies the original immutable evidence and a separate fresh recovery
authorization, but its latter authority has no permanent public archive contract.
Never modify the original immutable release. Enabling recovery requires another
reviewed implementation/contract; an approval string or runtime flag cannot enable
it in this driver. A failed or stranded immutable successor grants no new attempt,
expired-evidence reuse or current-pointer advance. Any future recovery needs a
separately approved permanent recovery-evidence contract.

## Installation authority

Independently approve remote executable eligibility using a separate
`RemoteInstallationPolicy` bound to the exact accepted Atlas publication policy
fingerprint. Publication approval alone cannot enable installation. The global
administrator reviews connector/version, package digest and catalogue identity;
the request additionally binds catalogue sequence/digest and numeric package asset.
Recheck live current ref and immutable package identity, genuine package
provenance, PackageStore archive safety, runtime compatibility/verification,
mappings, dependent configuration and existing local-authority restrictions.

Initially support remote writing only in Docker Compose. Native/systemd store
ownership is preserved; remote installation returns an explicit unsupported-mode
diagnostic. Already installed ordinary packages remain locally verifiable and
executable offline without a remote freshness dependency.

## Deployment independence and native compatibility

Catalogue documents/signatures, Connector Manifest and package distribution,
original package hash/Sigstore verification, approved publisher/history,
administrator authorization/review, compatibility/dependency validation, stored
package identity, Integration mappings, DataSources/source credentials, activation
history/audit and offline runtime verification remain deployment-independent.
Do not add Docker-specific fields to a Manifest or published catalogue. A future
native installer must consume the same immutable official release and bytes;
deployment choice must not require a replacement Connector or publication schema.

Compose may use its existing securely writable API package-store mount, with the
runtime mounting that store read-only. Native/systemd must retain the root-owned
protected store and dedicated unprivileged application/runtime accounts.

Future native remote installation requires a separately reviewed, narrowly
privileged staging boundary, such as a local installer service or constrained
one-shot systemd operation. It accepts only exact previously verified installation
requests and independently enforces request identity/authorization, replay and
filesystem boundaries. Reuse existing PackageStore verification, immutable tuple
layout, atomic staging and installation/activation contracts. Keep catalogue and
Connector business logic shared in the existing domain layer.

That design must not require a root API, broadly writable native store, package
installation authority in the Ansible runtime, shared signing/publication/GitHub
administrative credentials, unverified executable downloads inside the privileged
boundary, or duplicated catalogue authentication/Connector business logic.

**Capability boundary:** Compose is the supported remote-installation delivery
mode once its independent release/security approvals are satisfied. Native/systemd
remote installation is **unsupported** pending separate implementation and security
acceptance. Native operator-staged/bundled workflows remain supported under their
existing contracts. No privileged native staging service is implemented here.
See the [engineering assessment](../catalogue2-adr0018-approval-report.md) for the
current code boundaries, parity path and required acceptance.

## Authority and persistence

`APPROVED_FUTURE_POLICY`, its independent fingerprint, `APPROVED_REMOTE_INSTALLATION`
and its fingerprint are all unset. They can be accepted only in reviewed Atlas
release code. Downloaded JSON and producer trust settings cannot fill them.
The bootstrap approval remains unchanged. There is no sequence-two exception.

Walk bounded single-parent selection history to the independently approved root,
verify every signature/snapshot and contiguous pointer digest, and confirm the
current ref again. A fresh database can accept 1 then 2 in one transaction. Retain
original catalogue/signature/archive bytes, public observations and decision IDs
in existing immutable PostgreSQL revisions. High-water and identity/withdrawal
history remain monotonic. A failed later revision rolls back the entire new prefix.
Existing restore invalidates currentness; remote installation requires a new check.

Bounds are 32 revisions, 32 MiB total artifact input, 8 MiB evidence per revision,
a 240-second retrieval budget and 300-second refresh lease. Larger chains fail
closed and require a future reviewed incremental-history implementation; this is
not an unbounded or indefinitely scalable consumer.

## Inactive security remediation

The [remediation report](../catalogue2-security-remediation-report.md) records the
fresh 1→2 refresh and genuine-package activation regression: 34 + 6 = 40 anonymous
REST requests, plus fourteen official release downloads and fourteen CDN GETs.
Numeric release/asset identity remains API-bound. Only byte transfer uses strict,
application-constructed official release URLs with unchanged redirect/DNS, size,
digest and cryptographic verification. A bounded public observation set is private
to each operation; failures, refs and releases are not cached. Every original-run
check executes, and the final current ref is always reread without reuse.

Before an irreversible producer PATCH, require thirty seconds of remaining
publication-window headroom after the last slow read. Retain actual publication
time/identity verification afterward. This narrows write admission without extending
900/300-second historical limits. Provider delays or ambiguous writes can still
strand an immutable successor; current must remain unchanged on failed verification.
Those corrections granted no architectural approval or executable pins. The later
architectural acceptance recorded above also leaves executable pins unset.

## Activation and operational acceptance still required

Independent successor S/policy/identity pins and canonical approval fingerprints;
genuine successor signing/isolation review; anonymous published seven-asset and
interrupted-provider acceptance; and separately authorized new-LXC qualification.
Remote executable eligibility requires its own release-owned approval and audit.
Synthetic tests and existing genuine bootstrap/package artifacts cannot establish
these live facts. See the [engineering report](../catalogue2-engineering-report.md)
and [operator sequence](../deployment/catalogue2.md).
