# Official catalogue selection — sequence-one ingestion

Phase 3 connects the existing parser, independent Sigstore profiles, Phase 2A
public observations and Phase 2B restricted authorization to B1.3 refresh and
PostgreSQL acceptance. [Accepted ADR 0013](../../decisions/0013-sequence-one-consumer-bootstrap-approval.md)
records the owner's complete fixed consumer policy approval on 25 October 2026.
[ADR 0012](../../decisions/0012-official-catalogue-publication-authorization.md)
remains **Proposed** for the stronger future-publication evidence contract.

The first genuine live refresh accepted sequence one. The following live unchanged
attempt was rate limited; deterministic unchanged/API tests pass. Restart and
last-known-good checks succeeded. See the [operator record](../../deployment/official-catalogue.md#live-acceptance-record).
No package installation authority or new API/UI is introduced.

## Pointer structure

`parse_official_catalogue_selection(raw)` accepts literal bytes, length 1–1,024,
strict UTF-8/SDK JSON and exactly these fields:

| Field | Constraint |
| --- | --- |
| schema_version | Literal string `1.0` |
| sequence, release_id, asset_id | Positive literal integers, at most `2**53 - 1` |
| release_tag | Exactly `catalogue-{sequence:06d}` |
| sha256 | 64 lowercase hexadecimal characters |
| previous_pointer_sha256 | Null only for sequence one; otherwise a lowercase SHA-256 |

Duplicate keys, BOM/UTF-16/32, nonfinite numbers, booleans/floats for IDs and
unsupported fields fail. Canonical encoding must equal the **original bytes**:
UTF-8 `json.dumps(sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)`
plus one newline. The frozen `StructurallyValidSelection` retains original bytes
and immutable scalar fields; `pointer_sha256` hashes those bytes. Structure grants
no authenticity or package eligibility. The original parser supports later
sequences structurally; this ingestion adapter authorizes only sequence one.

## Independent selection signature profile

`GithubSigstoreVerifier.verify_selection(original_bytes, original_bundle)` uses
`official-catalogue-selection`, subject `current.json`, signer
`.github/workflows/catalogue-publish.yml@refs/heads/main`. Callers cannot select
issuer, workflow, subject, root or verifier. It reuses the integrity-checked CLI
**2.102.1**, frozen Public Good roots, isolated offline subprocess, bounded output
and 20-second deadline established by [ADR 0011](../../decisions/0011-offline-official-provenance.md).

Repository/owner numeric IDs, GitHub Actions issuer, hosted runner, SLSA v1,
certificate/signer/configuration/source/predicate consistency, exact original-byte
digest and transparency witnesses must agree. The invocation must be the fixed
repository's positive run ID and **attempt 1**. Catalogue (`catalogue.yml`) and
package (`release.yml`) profiles retain their separate identities and rules.

The original selection source is `8ce0b80c74d6ceb8ce75ac7ec8693f5bba78b305`, run
**39896288128**, attempt **1**. Original catalogue source is
`91dfd86f18d0b59ff977bb1e8a5fef42c5329943`. Neither is the separate activation
run/source or necessarily present main HEAD. Genuine frozen fixtures exercise both
profiles offline; parsed DSSE and producer receipts never substitute for crypto.

## Consumer-owned review and activation

`parse_catalogue_trust_policy_candidate()` remains a bounded review-schema parser,
not a policy loader. Explicit review inputs cannot authorize acceptance. Production
uses only the no-argument `approved_bootstrap_policy()` and existing
`AtlasApprovedBootstrapPolicy`. The exact original proposal and all nested pins
are compared against the independent release-owned SHA-256 in ADR 0013; the fixed
approval reference is `atlas-owner-2026-10-25-adr-0013`. The original version name
`atlas-bootstrap-consumer-policy-proposal-v1` is intentionally retained unchanged.

The approval covers the complete identity/signing pin set, not just the exception.
No producer policy, provider response, environment variable, URL, browser input,
secret or arbitrary approval string can select authority. Future policy changes
require a reviewed release. The complete pin inventory is recorded once in ADR
0013 and the fingerprinted code; the producer handoff is specification, never an
import or source of consumer authority.

## Phase 2A public provider observations

`verify_public_observations()` is unchanged: it independently reads and checks all
of the following through the existing anonymous bounded `GithubReader`:

- Latest run **and** original attempt one: exact numeric IDs, first attempt,
  manual main dispatch, authenticated source, repository/head repository, both
  human actors, workflow ID/path and API/HTML URLs. A latest rerun rejects.
- Independently resolved public User account matching the configured maintainer,
  active publication workflow, repository identity and protected main.
- Exactly one successful completed source `validate` check from Actions App
  **15368**. Historical source need not remain current main.
- Publication environment identity, no administrator bypass, protected branches,
  explicit supported protection rules and no required reviewers.
- Publisher App identity/owner and exact registered Contents Write plus Actions,
  Administration and Metadata Read permissions. Registration is not proof of
  effective installation/token permissions or historical privileges.
- Exactly five reviewed rulesets and each detail: numeric identity, repository,
  active enforcement, exact scopes, PR mode, strict CI and required locks.
  Present bypass arrays must match the reviewed empty or Publisher-only profile.

Missing bypass arrays remain `None`, never an inferred empty array. Frozen
`VerifiedPublicObservations` always retains `reviewed_ruleset_evidence_required`
and `consumer_trust_approval_required`, including within a successful bootstrap
exception. These partial observations are not general publication authorization.
Public settings cannot prove continuous historical protection or hidden bypass.

## Phase 2B restricted bootstrap authorization

`evaluate_bootstrap_exception()` requires the exact approved proposal/decision,
reparses original pointer bytes, binds genuine selection provenance/digest and
original signing invocation, then invokes all Phase 2A checks without waiving
other failures. Only omitted historical `bypass_actors` on the five pinned
rulesets may use `atlas-bootstrap-sequence1-exception-v1`. Contradictory arrays,
wrong actors, workflow, CI, source, environment, App, visible protections or
inaccessible evidence reject. No historical privileged evidence was recovered.

The distinct frozen `BootstrapExceptionAuthorization` retains policy, decision,
identity, selection, public observations, withheld ruleset IDs and the explicit
historical proof limitation. Its required-next-checks list describes that partial
component's boundary. The Phase 3 candidate separately completes acceptance
checks; package eligibility remains independent. Sequence two, a later publication
referencing sequence one, another root/source/run or substituted pointer cannot
use this exception.

## Immutable selection adapter and currentness

[`official_catalogue_ingestion.py`](../../../apps/api/app/services/official_catalogue_ingestion.py)
uses the existing reader and verifier. Fixed endpoint allowlisting admits the
current branch, bootstrap tag, exact-SHA Git objects/Contents, selected release and
numbered tag; no user ref or supplied URL is accepted.

1. Resolve `refs/heads/catalogue-current` and corroborating
   `refs/tags/catalogue-bootstrap-root` to the approved parentless root
   `a1597730687be993d766ddb465a0d3362aef2d02`. Check commit identity, no parents,
   exact two ordinary-file tree inventory and recomputed Git tree identity.
2. Read `current.json` and `current.sigstore.json` at that exact commit. Contents
   responses require exact path/name/API URL/blob SHA, file type, literal bounded
   size and supported base64. Decode strictly, reject noncanonical base64/padding,
   check decoded size and recomputed Git blob SHA. Provider download URLs are
   ignored. Preserve the original bytes; independently verify their signatures.
3. Apply the restricted authorization, then read release **421426993**, exact tag
   `catalogue-000001`, non-draft/non-prerelease and actual `immutable: true`.
   Require exactly the original four assets with unique IDs, names, API/browser
   identities, uploaded state, bounded size and SHA-256. The catalogue asset must
   be **667867351** and match both the signed pointer and approved catalogue digest.
4. Download bounded original catalogue and build bundle through the existing
   asset downloader. Validate v1/SDK Manifests and canonical original bytes.
   Authenticate the catalogue with its own B1.2 profile and original build source;
   the selection signature cannot replace this build evidence. Resolve the release
   tag (bounded annotated-tag support) to that source and check target_commitish.
5. Retrieve retained `current.json` and signature assets and require exact equality
   with the ref-selected originals. Before persistence, freshly reread immutable
   release/all asset identities, the original pointer at its commit, then the
   authoritative current ref. A changed ref, selection, release or asset rejects.
   Immutable root/tree/bundle identities need no duplicate metadata reads.

Only completion mints a frozen `VerifiedBootstrapCandidate` with an internal seal
and refresh UUID. Replacing/constructing its fields does not mint the seal.
Promotion requires that type/seal, this operation's UUID, the exact approved
identity, matching original bytes/profiles/sources and a recent confirmation.
Arbitrary metadata dictionaries and the legacy `catalogue-v1` adapter retain their
publication rejection. This is an internal evidence boundary, not protection
against arbitrary Python execution.

The existing 90-second retrieval deadline, 150-second lease, cooldown, PostgreSQL
locking, audit and restore coordination remain. No cached signature or historical
release can renew currentness; a newer unapproved root rejects without falling
back to sequence one. Missing history, gaps and conflicts fail closed. See the
[trust-store/operator contract](../../deployment/official-catalogue.md) for durable
evidence, recovery, limitations and API results.

## Remaining boundaries

Future publication sequences need the separately reviewed stronger evidence
contract in ADR 0012, contiguous signed predecessor history and later transition
implementation. Full-database rollback cannot be excluded from that database
alone. No external checkpoint service is added.

Catalogue trust is not package trust. The active historical Proxmox 0.2.0 entry
is accepted metadata; its mutable package remains unavailable for remote download,
install, upgrade or execution. Bundled/installed Proxmox remains unchanged.
The Integrations catalogue UI now displays this metadata read only; see the
[UI operation contract](../../deployment/official-catalogue.md#integrations-catalogue-ui).
A newly published immutable connector package with separate eligibility/explicit
installation authority remains a later milestone.
