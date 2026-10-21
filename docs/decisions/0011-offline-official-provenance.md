# 0011 — Pinned offline official provenance verification

Status: **Accepted**

Date: 2026-10-21

## Context

[ADR 0006](0006-verified-connector-supply-chain.md) requires authenticated
official provenance and immutable publication before remote package execution.
B1.1 validates catalogue structure only. Its declarations cannot authenticate
the publisher or authorize executable bytes. B1.2 explicitly approves a maintained
verifier and reviewed roots, without retrieval, persistence or installation.

## Decision

Distribute GitHub CLI 2.102.1 with pinned archive and extracted-binary SHA-256
identities through Atlas's existing API image and native installation boundary.
Use a fixed application-owned executable path and a frozen, pinned Sigstore
Public Good trusted root. Runtime verification uses local files only. No PATH,
user CLI, token, network root refresh or caller-selected trust configuration is
permitted. The execution runtime and discovery worker need no verifier binary.

Authenticate the independently established repository and owner numeric IDs,
repository URI, issuer, exact signer/configuration identity, source ref/commit,
hosted runner, SLSA predicate and original-byte subject digest. Catalogue and
package profiles use different workflows. Certificate identity is stronger than
workflow-supplied signed predicate claims; check their consistency without
claiming independently proven build correctness.

Return immutable typed provenance evidence, separate from structural validity
and existing package installation evidence. No attestation alone establishes
release approval, immutable history, freshness, eligibility or authorization.
Keep the legacy installer unavailable for remote packages until the later
catalogue acceptance and package eligibility adapters are implemented.

Trust-root and verifier changes require reviewed Atlas releases, supported-platform
digests and genuine offline acceptance. There is no unattended root replacement.
Offline deployments cannot learn subsequent revocations without an upgrade.

## Alternatives and consequences

A custom cryptographic implementation adds unnecessary security responsibility.
System-installed CLI discovery permits uncontrolled verifier drift. Downloading
trust policy from the catalogue would make the trust bootstrap circular.

A pinned verifier/roots snapshot intentionally stops accepting new unsupported
evidence until a reviewed upgrade. Self-hosted runners, private Sigstore instances,
reusable signer workflows and other issuers are outside this initial policy.
Changing those identities requires a deliberate policy change.

This refines ADR 0006 rather than superseding it. Mutable existing GitHub releases
remain a separate publication gap. See the [implementation and operator contract](../deployment/attestation-verification.md)
and feature ledger for actual delivery and acceptance limits.
