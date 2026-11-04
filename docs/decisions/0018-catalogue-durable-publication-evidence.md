# 0018 — Durable original publication evidence and remote installation

Status: **Proposed — owner/security approval required**

Date: 2026-11-04

This supplements Proposed ADR 0012. It does not amend or accept it, extend the
sequence-one exception in Accepted ADR 0013, or supersede ADRs 0006/0011/0015/0016.
Code implementing this proposal is inactive behind Atlas-owned approval boundaries.

## Proposed decisions

1. Future ordinary sequences carry exactly seven immutable assets: numbered
   catalogue, catalogue bundle, original current pointer/bundle, original v2
   preflight/bundle and exact source policy. Authenticate original bytes with
   Atlas's independently pinned verifier/roots, successor signer S, exact policy
   digest, numeric identities, original source C and first-attempt run. A release
   archive, producer policy, receipt, environment or request cannot select Atlas
   authority. The pure signed-observation validators are Atlas-owned copies of
   the existing producer contract, with no administrative transport or credentials.
2. Require original signed observation ordering and at most 900 seconds from
   observation start through expiry. Require all verified preflight transparency
   times within issuance/expiry, original run creation before observations, all
   selection witnesses after preflight witnesses, selection within a proposed
   **900 seconds** of issuance and publication within a proposed **300 seconds**
   of selection. Supported Tlog witnesses come from the existing pinned roots
   and two allowlisted log URIs; one through eight verified witnesses are accepted,
   not a two-log quorum. These are proposed bounds, not owner-accepted defaults.
   Historical evaluation never admits an expired live job or proves continuous
   protections. GitHub `published_at` remains transport metadata, not a signed time.
3. Accept selection binding only if separately reviewed: original preflight and
   independently signed selection have identical C/run/attempt; build signature
   and release tag agree on C; retained selection/bundle are byte-identical in
   that immutable seven-asset release; and the reviewed publisher enforces one
   selection per source. The consumer also rejects source reuse within its chain.
   The preflight does **not** directly sign a later pointer or numeric asset IDs.
   This reliance on reviewed implementation/co-location must be explicitly accepted.
4. Keep production recovery **disabled pending a permanent recovery-archive
   decision**. The inherited recovery evaluator verifies the original immutable
   evidence and a separate fresh recovery authorization, but its latter authority
   has no permanent public archive contract. Never modify the original immutable
   release. Enabling recovery requires another reviewed implementation/contract;
   an approval string or runtime flag cannot enable it in this driver.
5. Independently approve remote executable eligibility using a separate
   `RemoteInstallationPolicy` bound to the exact accepted Atlas publication policy
   fingerprint. Publication approval alone cannot enable installation. The global
   administrator reviews version, package digest and catalogue identity; the
   request additionally binds catalogue sequence/digest and numeric package asset.
   Recheck live current ref and immutable package identity, genuine package
   provenance, PackageStore archive safety, runtime compatibility/verification,
   mappings, dependent configuration and existing local-authority restrictions.
6. Initially support remote writing only in Docker Compose. Native/systemd store
   ownership is preserved; remote installation returns an explicit unsupported-mode
   diagnostic. Already installed ordinary packages remain locally verifiable and
   executable offline without a remote freshness dependency.

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
These implementation corrections do not accept this proposed ADR or populate pins.

## Acceptance still required

Owner decisions on each item above; independent successor S/policy/identity pins;
genuine successor signing/isolation review; anonymous published seven-asset and
interrupted-provider acceptance; and separately authorized new-LXC qualification.
Synthetic tests and existing genuine bootstrap/package artifacts cannot establish
these live facts. See the [engineering report](../catalogue2-engineering-report.md)
and [operator sequence](../deployment/catalogue2.md).
