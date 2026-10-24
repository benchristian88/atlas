# 0012 — Official catalogue publication authorization

Status: **Proposed**

Date: 2026-10-25

## Context and delivered boundary

[ADR 0006](0006-verified-connector-supply-chain.md) requires approved immutable
publication before execution. [ADR 0011](0011-offline-official-provenance.md)
approves the pinned offline verifier, not a publication authorization policy.
An authentic signature establishes the signer, source and exact artifact bytes;
it does not establish the authorizing human, CI, protection settings, selected
release, currentness or executable eligibility. Neither accepted ADR is rewritten.

Phase 1 authenticates `current.json` under its distinct selection profile.
Phase 2A adds an internal evaluator of independently retrieved **public** GitHub
observations against that evidence and explicitly supplied review expectations.
Its frozen `VerifiedPublicObservations` always retains unresolved authorization
blockers. There is no approved policy instance, authorization function, new route,
database change or path to promotion. See the
[component contract](../architecture/integrations/official-catalogue-selection.md).

The boundaries remain: structural pointer validity; cryptographic authenticity;
verified public observations; complete reviewed publication authorization; trusted
catalogue acceptance; executable package eligibility. Only the first three have
components here. A review-schema candidate is never an active trust policy.

## Proposed assurance and consumer authority

`single-maintainer-v1` would mean one explicitly authorized ordinary GitHub user
manually dispatches publication. Both original and triggering actor IDs must equal
the consumer-owned maintainer ID. A matching public account lookup must confirm
ID, login and User type. Ownership never chooses the maintainer. This offers no
second-person veto and no identification of a person behind an App-triggered tag.

Atlas must separately approve repository/owner, maintainer, environments,
Publisher App/slug/bot, workflow and ruleset numeric identities, bootstrap
sequence/exact pointer digest, reviewed producer revision, verifier implementation
S, issuer, hosted runner and release-owned verifier/roots. Producer policy,
responses, receipts, current main and environment variables cannot select these
authorities. Phase 2A takes explicit review inputs for evaluation only; no defaults
or activation mechanism are added.

The selection certificate's original invocation identifies the run. Independent
latest-run **and** first-attempt GETs must agree on numeric run/attempt 1,
`workflow_dispatch`, main, authenticated SHA, repository/head repository,
actors, workflow and exact API/HTML URLs. A latest attempt 2 rejects even when
attempt 1 survives. The independently retrieved active workflow must be exactly
`catalogue-publish.yml`; supported original-run paths are only the exact path,
path`@main` and path`@refs/heads/main`. The separate source `validate` CI must be
unique, completed/successful on the authenticated SHA, from Actions App 15368.
Historical source need not equal present main HEAD. Run completion itself is not
required: a signature can survive an interrupted publication job.

## Ruleset visibility and inspected producer evidence

GitHub [documents](https://docs.github.com/en/rest/repos/rules#get-a-repository-ruleset)
that `bypass_actors` is returned only to a principal with write access to the
ruleset. An omitted field is unavailable evidence, never `[]`. Anonymous reads
can establish visible identities, active enforcement, scopes and rule parameters,
but cannot establish complete bypass authority. Administration Read is insufficient.

Inspection used the unchanged producer checkout at
`b03405d6acfd562f75dbdf7aad91c94df9a1d32e`, including its handoff, runbook,
[ADR 0004](https://github.com/benchristian88/atlas-connectors/blob/b03405d6acfd562f75dbdf7aad91c94df9a1d32e/docs/decisions/0004-isolated-signed-publication-verifier.md),
[ADR 0005](https://github.com/benchristian88/atlas-connectors/blob/b03405d6acfd562f75dbdf7aad91c94df9a1d32e/docs/decisions/0005-lean-run-preflight.md),
`tools/publication_authorization.py`, `tools/issue_publication_authorization.py`,
`tools/authorization_sigstore.py` and both publication workflows. They are
specification/evidence, not runtime imports or automatic Atlas trust.

The isolated Verifier App (5424851) has Administration Write plus Contents,
Actions, Checks and Metadata Read. Its restricted transport observes repository
data through GETs and uses one fixed POST to mint its installation token. Its key
is isolated from Publisher jobs. That implementation limitation does not reduce
the credential's real ability to alter protections if stolen. The Publisher App
(5422372) has the baseline Contents Write; Actions/Administration/Metadata Read.
Public App registration metadata cannot establish effective installation/token
permissions or the historical absence of temporary Workflows Write.

The S4 implementation pin is `2dd1ffcd2f5677dc35bdbc8f68ea28275c91c285`.
The producer's canonical `atlas-publication-preflight/v2` signs:

- Repository, owner, maintainer and both App/installation IDs.
- Caller source C, exact policy-byte SHA-256, verifier implementation S/path.
- Caller workflow, original run/attempt, operation and acceptance-only boolean.
- Repository/main/run/attempt/workflow/account/CI, both environments, Publisher
  metadata and release-immutability setting observations.
- All five pinned ruleset IDs, complete detail observations including bypass
  arrays, canonical observation digest and expected bypass actors.
- Observation start/completion, issue time and expiry.

Its distinct subject is `preflight.json`, predicate
`https://atlas-impact.dev/attestations/publication-preflight/v2`. The predicate
repeats its exact-byte digest. The reusable signer authenticates S separately
from caller/buildConfig/source C and original invocation. These are different
claims from the existing selection signature. Atlas implements no preflight
signature profile in Phase 2A.

Fresh startup admission lasts at most 900 seconds from the earliest privileged
observation; a runner-local admission receipt allows at most 30 minutes of
same-job work with repeated signature/context verification. That receipt is not
portable authorization. Later read-scoped rechecks cannot detect withheld bypass
changes. Preflight is neither an atomic GitHub transaction nor proof of continuous
protection, and contains **no pointer digest, selected release or asset IDs**.

The workflow registers the attestation and uploads the two preflight files as an
Actions artifact with **one-day retention**. Attestation registration authenticates
the preflight digest; it does not promise permanent availability of the preflight
bytes. The [artifact download API](https://docs.github.com/en/rest/actions/artifacts#download-an-artifact)
uses an expiring redirect and authenticated access; a public artifact listing is
not an anonymous immutable archive. Current Publisher/bootstrap code requires
the four catalogue/bundle/selection/bundle release assets and does not archive
the preflight pair or exact policy bytes there.

Bounded anonymous GETs on 25 October 2026 corroborated original run 39896288128
and attempt 1, source `8ce0b80c74d6ceb8ce75ac7ec8693f5bba78b305`, workflow
392548804, and the publication environment. The run artifact inventory exposed
only `catalogue-publication-receipt` (12476678827), not the preflight pair.
Immutable release 421426993 exposed only the four original assets, IDs
667867351, 667867380, 667867419 and 667868363. This does not rule out a separately
preserved archive, but no such publicly retrievable genuine pair was established.
No receipt was treated as a signed substitute. Public ruleset details omitted
bypass actors. The full Phase 2A evaluator subsequently returned consistent public
observations, including successful source check 120223477245 from Actions App
15368, matching human account and baseline Publisher permissions, with both
authorization blockers retained. These observations are corroboration, not
historical authorization. Normal CI tests use mocked HTTP and genuine offline
selection fixtures, never live provider calls.

## Options and recommendation — not approved

| Option | Benefit | Limit / requirement |
| --- | --- | --- |
| A: authenticated producer evidence | Reuses the isolated S4 signer and complete privileged snapshots; keeps distributed Atlas anonymous | Requires preserved genuine bytes/bundle, independently reviewed S/policy, exact context binding and a deliberate change to Atlas's independent-observation requirement for hidden fields |
| B: authenticated consumer observation | Retrieves full present-day bypass data independently | Requires write-level administrative access to a producer-owned repository; distributing such credentials to self-hosted instances creates an unacceptable shared credential/administration boundary for the default deployment |
| C: continue rejecting incomplete evidence | Preserves all accepted trust boundaries with no new privilege | Catalogue acceptance stays unavailable until an approved, retrievable provider-evidence contract exists |

Recommend **A as the smallest future contract amendment, with C remaining the
current behavior**. Do not implement A through a permissive receipt parser,
unsigned snapshot, new consumer token fallback or this proposed ADR. B could
only be a separate explicitly reviewed administrative deployment design, not
an automatic fallback; Read-only permissions would not solve the hidden field.

Before A can be approved, amend the producer handoff/publication contract to
preserve exact preflight bytes, bundle and corresponding policy bytes in bounded,
public, immutable release assets. Use the existing S4 signature format where
feasible, pin S independently, and correlate exact run/attempt/source/operation
with the genuine selection invocation. The selection signature binds the pointer;
independent immutable release/asset checks must bind its selected catalogue and
retain that identical selection. Archival filenames/receipts alone bind nothing.
Review pinned code's one-selection-per-run behavior; never claim the current
preflight directly signs the later pointer or release IDs.

Bootstrap needs both original staging evidence and the **separate activation**
run's evidence/policy, whose approved exact pointer digest must match the original
selection. Activation invocation/source cannot replace the selection signer.
Ordinary recovery also needs explicit original-selection versus recovery-run
context. Specify bounded inventories, immutable archive identity and failure
behavior before changing the producer's four-asset inventory contract.

Sequence one's immutable release cannot be amended. A separate reviewed immutable
evidence release or consumer-distributed archive could preserve an already
captured genuine pair, with exact digests and context verified independently.
If that evidence was lost, current observations or a new retrospective signature
cannot recreate historical observations. Historical acceptance remains blocked
pending an explicit security decision; do not rewrite catalogue bytes/signatures
or manufacture a replacement preflight. No producer changes are made here.

Archived evidence could support **publication-time** verification if its original
signature, full bypass lists, S, exact policy/context and time bounds are verified.
It cannot satisfy the existing live startup API by simply extending expiry.
Approve a distinct historical evaluation rule that evaluates observation/issuance
and verified transparency times against the original run/publication, while
retaining live public rereads for present-day state. Neither archival snapshots
nor present-day public settings exclude a hidden bypass added after preflight,
temporary protection disablement, later environment/App changes, credential
compromise or withholding of a newer selection. A requirement for full **current**
bypass state would still block A; reviewers must explicitly decide that tradeoff.

## Knowledge, executable eligibility and restore

Proposed historical sequence-one acceptance would accept authenticated catalogue
knowledge containing Proxmox 0.2.0, not permission to execute that package. Its
original mutable package release remains ineligible. A later phase must separately
review generic entry eligibility against immutable package release/asset identity,
source/tag/provenance, runtime/SDK compatibility, current accepted catalogue and
explicit installation authority. No Proxmox-specific bypass, Manifest rewrite,
bootstrap installation change or executable-store change is permitted here.
Implementing that distinction remains later work, rather than a Phase 2A feature.

Future acceptance must retain original bytes/evidence, consumer policy identity,
contiguous predecessor/high-water history and sticky withdrawals atomically.
After restore, invalidate currentness and revalidate provider evidence, immutable
identities, approved policy, chain and conflicts before renewing trust or allowing
remote eligibility. Cached signatures/public observations cannot renew freshness.
Existing retained-revision recovery cannot detect rollback of the **entire**
database and all checkpoints together. Absolute rollback protection would need an
independent durable checkpoint outside that backup boundary, which is not added
or claimed by this proposal. Missing history must require reviewed recovery, not
rebootstrap or deletion of trusted state.

## Required human decisions and remaining risks

Reviewers must approve the single-maintainer assurance level and actual Atlas
authority/bootstrap/S pins; decide whether authenticated producer observation may
satisfy hidden publication-time fields; approve archive availability and historical
freshness/binding rules; resolve sequence-one evidence availability; and separately
review acceptance/history/restore and package eligibility before activation.
If these decisions change ADR 0006/0011 boundaries, follow the supersession process.
Acceptance of this ADR would still not demonstrate implementation or live acceptance.

Compromise of the sole maintainer, repository administrator, GitHub/OIDC/Sigstore
trust infrastructure, accepted S/action/dependency, privileged Verifier key or
Publisher credential remains relevant. Isolation and signed observations reduce
specific risks but cannot prove uninterrupted settings, human independence or
correctness of trusted code. Immutable publication protects retained bytes, not
all surrounding provider state. Phase 2A preserves rejection until these explicit
decisions and later implementation/acceptance are complete.
