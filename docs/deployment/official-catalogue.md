# Official catalogue retrieval and durable trust

The [official catalogue approval and operator sequence](catalogue2.md) records
the active release-owned publication and separate Docker Compose installation
policies under [accepted ADR 0018](../decisions/0018-catalogue-durable-publication-evidence.md).
Atlas follows authenticated `catalogue-current` and verifies complete sequential
signed history. Catalogue 2 and later valid releases from the same approved
authority need no per-sequence approval change. Eligible new Connectors/versions
require individual global administrator review and exact confirmation before
genuine package verification and installation. Native remote writing remains
unsupported; existing operator staging/offline operation is preserved. Automatic
refresh remains disabled. Fresh LXC ingestion/installation is not yet qualified.

The sections below document the **preserved sequence-one bootstrap profile** and
its original acceptance, under [accepted ADR 0013](../decisions/0013-sequence-one-consumer-bootstrap-approval.md).
The linked operator sequence supplies later-release bounds, approval fingerprints
and installation procedure. The broader
[ADR 0012](../decisions/0012-official-catalogue-publication-authorization.md) remains Proposed.

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
| Invalid or unapproved selection | Failed; no new trust; later releases require the separate future-publication policy |
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

## Integrations catalogue UI

**Integrations → Catalogue** uses one responsive `ConnectorCard` per Connector
identity. The page requires `integrations.view`. A global
`integration_runtime.view` assignment additionally loads retained official status
and locally verified installed Manifest display metadata; scoped assignments do
not grant this access. A global `integration_runtime.manage` assignment exposes
catalogue checks and eligible package-management actions. Backend authorization
remains authoritative.

The presentation reconciliation layer keeps each package identity intact:

- Installed packages use their own locally verified Manifest name, description,
  category, publisher, licence, version and verification state. They remain visible
  offline, including identities absent from the bundled catalogue. Failed local
  verification retains the installed identity with an explicit unavailable warning,
  rather than borrowing another version's metadata.
- Otherwise, the newest active accepted official release supplies primary metadata,
  ordered by semantic version precedence. An installed package can show a different
  available official release separately. No bundled digest, verification state or
  action eligibility is transferred to an official release.
- Bundled packages and planned metadata-only Connectors provide the offline fallback.
  New official identities appear automatically. Withdrawn and other official releases,
  plus historical bundled packages, remain in expandable per-card release history.
  A withdrawn-only identity without a fallback is visibly withdrawn and cannot be
  installed from official history.

The existing `GET /api/integration-catalogue` response retains its `entries` and
adds `installed_entries`. This display-only projection is populated only for a
global runtime viewer. It uses existing local PackageStore verification, includes
only selected Manifest fields, and requires neither remote freshness nor resolved
mappings. It adds no installation authority or new installation API.

- **Reload displayed catalogue** rereads local page data and retained official status.
  It never starts a remote official check.
- **Reload official status**, within publication diagnostics (or visible when status
  cannot load), reads retained backend state without contacting GitHub. Use it after
  another administrator's check or after a cooldown expires.
- **Check for catalogue updates** explicitly invokes the existing authenticated
  remote verification API. Opening the page only reads status. There are no automatic
  retries, polling or periodic remote checks.

The restrained status area shows the accepted sequence and last successful source
confirmation. Retained acceptance is labelled previously accepted; only a successful
`accepted` or `unchanged` result in this session is labelled freshly confirmed by
that check. Neither establishes that the remote source is still unchanged. A missing
confirmation (including after restore) is **Not recorded**. Catalogue digest, schema
and stage timestamps remain in expandable publication evidence and diagnostics.

Verification failures retain accepted metadata and its historical confirmation.
Request errors remain distinct from verification failures. Permission denial clears
the official display while bundled cards remain usable. Pending operations suppress
duplicate remote checks; cooldown/rate-limit messages retain the backend's next
permitted time. Reload after that time; there is no cooldown bypass.

Official installation requires the backend's separately approved exact selection.
The administrator reviews Connector identity, version, catalogue sequence/digest,
package digest and release asset, then explicitly confirms. The unchanged installation
API independently reselects and revalidates every field, live currentness, provenance,
compatibility, mappings, dependent configuration and activation/audit. Installed
packages do not show a redundant review action for the same version and digest.
Resolve mappings uses the installed version when present. Withdrawn Proxmox 0.2.0
is historical metadata only; the preserved bundled 0.1.0 package retains its offline
contract. No version, sequence or Connector-specific eligibility is hardcoded in
presentation reconciliation.

This UI does not add cryptographic guarantees: verification and trust decisions
remain backend responsibilities under ADR 0013 and ADR 0018. The future-publication
and remote-installation approvals are recorded separately in the operator sequence;
scheduling, native remote writing and community catalogues remain outside this scope.

## Historical sequence-one live acceptance record

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

Later sequences use the approved stronger publication evidence/archive contract.
Current approval records, the existing immutable Proxmox 0.2.2 package and pending
fresh deployment qualification are documented in the linked operator sequence.
Secure installation retains separate genuine package provenance/immutable identity,
runtime/SDK compatibility, current catalogue eligibility, explicit global
administrator authority and protected-store validation. Daily scheduling remains
later work. The historical acceptance harness above qualifies its original
sequence-one scenario; use the current operator sequence for a fresh deployment.
