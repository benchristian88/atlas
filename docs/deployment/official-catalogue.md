# Official catalogue retrieval and durable trust

The existing global refresh API now retrieves and accepts the genuine immutable
**sequence-one** catalogue under the complete owner-approved policy in
[Accepted ADR 0013](../decisions/0013-sequence-one-consumer-bootstrap-approval.md).
Future sequences fail closed pending the stronger publication evidence contract
in [Proposed ADR 0012](../decisions/0012-official-catalogue-publication-authorization.md).
Remote package installation and automatic refresh remain disabled.

## Source and trust policy

Atlas-owned version-controlled code exclusively selects the source and trust
pins. `approved_bootstrap_policy()` verifies the exact unchanged proposal's
fingerprint and returns `AtlasApprovedBootstrapPolicy` with fixed decision
`atlas-owner-2026-10-25-adr-0013`. Operators cannot configure trust through tokens,
environment settings, downloaded policies, URLs, approval strings or refresh flags.

The adapter uses fixed anonymous GitHub API endpoints in
`benchristian88/atlas-connectors`:

- `git/ref/heads/catalogue-current` and corroborating
  `git/ref/tags/catalogue-bootstrap-root`, both pinned to parentless commit
  `a1597730687be993d766ddb465a0d3362aef2d02`.
- Exact-SHA Git commit/tree and Contents reads for the two original selection
  files. Strict UTF-8/unambiguous JSON, base64, path, size and Git blob/tree identity
  checks precede genuine verification. Returned download URLs are never followed.
- The original selection signing run **39896288128**, attempt **1**, plus all
  independently checked public identity/workflow/CI/protection evidence.
- Selected release **421426993**, tag `catalogue-000001`, actual `immutable: true`,
  non-draft/non-prerelease, catalogue asset **667867351**, and its three retained
  signature/selection assets. Exact original catalogue digest is
  `55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd`.

The [selection contract](../architecture/integrations/official-catalogue-selection.md)
describes the full checked identity/transport pipeline. The original catalogue
signature is independently verified under B1.2, including build source
`91dfd86f18d0b59ff977bb1e8a5fef42c5329943` and release-tag/source binding. It is
separate from selection provenance and the activation dispatch. v1 structure,
SDK Manifests and producer-compatible canonical original bytes are required.
Retained release selection/signature bytes must equal the ref-selected originals.

Only missing historical `bypass_actors` for the five approved rulesets may use
`atlas-bootstrap-sequence1-exception-v1`. Every other missing, inaccessible or
contradictory observation rejects. Public arrays are never inferred empty;
Phase 2A retains its partial-authorization blockers. No hidden historical evidence
was recovered and no uninterrupted protection is claimed. Single-maintainer
approval supplies no independent second-person veto.

The legacy `catalogue-v1` adapter is retained for rejection regressions. Mutable
legacy publication still fails `publication_not_immutable`; even an immutable
legacy alias fails `current_channel_policy_unavailable`. It supplies no authority
through a publication dictionary or partial proof.

## Bounds and currentness

| Resource | Bound / policy |
| --- | --- |
| Original catalogue | 4 MiB, at most 200 entries; canonical per-entry 256 KiB |
| Pointer | 1,024 bytes, canonical original JSON |
| Each original Sigstore bundle | 1 MiB |
| Ordinary metadata / Contents envelope | 256 KiB / 2 MiB |
| Persisted publication evidence | 3 MiB application bound; lossless base64 originals |
| Connections / connect / read / request | Two / 5 / 5 / 15 seconds |
| Entire retrieval / verifier subprocess | 90 seconds / 20 seconds reserved per profile |
| Refresh lease / cooldown | 150 seconds / 15 minutes, durable instance-global state |

The existing reader disables ambient authentication, proxies, cookies and
decompression; validates HTTPS/public DNS; bounds streamed and declared lengths;
rejects metadata redirects/pagination; and permits one binary API 302 only to
`release-assets.githubusercontent.com`. No credential fallback exists. Rate limits
honor Retry-After/reset in durable next-attempt state without long request sleeps.

Before promotion, reread release/all selected asset identities, original pointer
bytes at the exact commit and finally the authoritative current ref. Require
unchanged selection/transport identity. A newer unapproved selection rejects;
sequence one is never used as a fallback. The first-attempt public checks and both
signatures are rerun for unchanged refreshes. Cached evidence or historical
immutable-release availability cannot renew currentness.

## Persistence, history and restore

No new migration is required. Existing migration `20261021_0031` provides the
singleton checkpoint and append-only immutable revisions. PostgreSQL UPDATE/DELETE
revision guards and checkpoint monotonic/composite-FK constraints are unchanged.

A short advisory/row-lock transaction claims the UUID/lease. Network and crypto
run outside row locks. Finalization reacquires the lock, validates ownership and
lease, checks the completed typed operation-bound candidate and trusted history,
then commits revision/checkpoint/audit together. Lost ownership, interrupted
refresh, insertion or audit failure cannot partially promote. An unchanged verified
selection updates currentness without creating a second revision.

The revision retains:

- Original catalogue bytes in `original_bytes`, digest, schema/sequence,
  generated_at and accepted_at.
- Both bounded verified profile results in `verification_evidence` (below its
  existing 64 KiB constraint).
- Original pointer and both original bundles losslessly base64-encoded in
  `publication_evidence`, pointer/catalogue digests, release/asset identities,
  authenticated transport/root/tag binding, approval/exception/decision,
  sanitized typed public observations, withheld ruleset IDs, historical limitation
  and confirmation/observation timestamps. Signed download URLs, CLI output,
  credentials and executable packages are excluded.

Promotion cannot be authorized with an arbitrary dictionary. It requires the
completed immutable candidate minted only after all checks, the matching refresh
UUID and a recent confirmation. The underlying private storage primitive remains
available for explicitly unauthenticated storage unit fixtures, not API callers.

| Transition | Result |
| --- | --- |
| Empty trusted store, exact approved sequence one | Accepted after all trust gates |
| Same authenticated original selection | Unchanged; one retained revision |
| Invalid or unapproved selection, including sequence two | Failed; no new trust |
| Lower/same-sequence substituted catalogue | Conflict; retained trust preserved |
| Sequence gap or incomplete/inconsistent retained history | Reject; reviewed recovery required |
| Transient provider/verifier failure | Retain last-known-good without renewing currentness |

Contiguous retained revisions and original-byte digests are checked during refresh,
with a 1,000-revision/20-second processing bound. Identity history retains complete
Manifest/tag/asset identity and sticky withdrawals even when later omitted. No
version may silently change identity or reactivate after withdrawal. Recovery can
reconstruct a missing/older checkpoint from consistent retained history and clears
currentness. Missing retained history never authorizes rebootstrap.

The existing shared `normal_operation` lock spans refresh and drains before
restore. Restore finalization preserves accepted revisions/history but clears
`last_confirmed_current_at`, refresh ownership/lease and cooldown. Renewed full
live verification is required. Historical acceptance and freshness are distinct.
**Rollback of the entire database and all its checkpoints cannot be proven absent
using that database alone.** No independent checkpoint service is added.

## API and operations

| Existing route | Required global permission |
| --- | --- |
| `GET /api/integration-catalogue/status` | `integration_runtime.view` |
| `POST /api/integration-catalogue/refresh` | `integration_runtime.manage` |

Refresh accepts no body or `{}`, and no selection/query parameters. Scoped users
cannot inspect or refresh instance-global trust. Existing 401/403/422 contracts,
restore/maintenance coordination and tenant boundaries are unchanged. Results are
`accepted`, `unchanged`, `in_progress`, `cooldown` or `failed`. Ordinary verification
failure uses HTTP 200 with explicit result/diagnostic; persistence/ownership errors
may return a safe top-level code.

After acceptance status reports `trusted_remote_available: true`, sequence **1**,
the exact digest above, original generation time, acceptance/currentness/stage
timestamps and policy `atlas-bootstrap-consumer-policy-proposal-v1`. Read-only
accepted entries have `package_available: false` and no supported actions.
Historical Proxmox 0.2.0 is metadata only: its original package release is mutable,
and catalogue acceptance neither downloads nor makes it installable/upgradable/
executable. The bundled and installed connector are unchanged. No UI redesign or
installer provider change is included.

On `source_rate_limited`, honor `next_attempt_at`. On root/selection/release/asset
conflict or `checkpoint_inconsistent`, preserve history and investigate; do not
delete state or override trust. Fix missing verifier/roots through reviewed release
packaging. No failure renews currentness; an older confirmation remains historical.

## Live acceptance record

On **25 October 2026, 11:20 NZDT**, the opt-in anonymous read-only GitHub acceptance
using an empty disposable PostgreSQL 17 database and the existing refresh API
accepted sequence **1**, digest
`55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd`.
Both actual pinned verifier profiles passed; the immutable release, original
selection/build sources and all public observations were checked. The following
full live unchanged attempt hit `source_rate_limited`; **live unchanged acceptance
was not completed**. Deterministic genuine-crypto API tests verify unchanged
acceptance without duplicate revisions.

The disposable PostgreSQL server was restarted. Reopened state retained the exact
revision/evidence; both retained signatures reverified offline. The status API
returned the accepted sequence/digest and non-installable metadata. A simulated
later source failure preserved that state and the original confirmation time.
No production data, GitHub credentials, mutations, workflows or connector packages
were used. The source reads were subsequently reduced to avoid redundant immutable
metadata rereads while retaining final pointer/release confirmation.

## Validation and next increments

From `apps/api`, with an **empty disposable** `atlas_b13_*` or `atlas_test_*`
database in `ATLAS_TEST_DATABASE_URL` and private temporary `ATLAS_STATE_DIR`:

```bash
python -m scripts.accept_official_catalogue --allow-live-github --disposable-database
```

The harness refuses nonempty databases, migrates, invokes existing refresh/status
APIs, controls cooldown only in this disposable environment, repeats full refresh,
reopens connections and simulates later unavailability. It reports
`milestone_accepted` separately from `complete_live_acceptance` and exits nonzero
if the second live verification fails. Anonymous provider limits can prevent the
second verification; no cached-evidence shortcut or token fallback is allowed.

Future sequences need the stronger reviewed publication evidence/archive contract.
Next product work is to surface trusted metadata in Integrations and prepare a
new immutable connector package. Secure installation still needs separate generic
package provenance/immutable identity, runtime/SDK compatibility, current accepted
catalogue eligibility, explicit global administrator authority and protected-store
validation. Daily scheduling and installation freshness policy remain later work.
