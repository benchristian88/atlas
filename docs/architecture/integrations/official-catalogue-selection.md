# Official catalogue selection — Phases 1 and 2A

Implemented internal components: strict pointer parsing, a separate offline
selection provenance profile, consumer-policy **review schema** and independent
public GitHub observation evaluation. These extend
B1.1/B1.2 without connecting to B1.3 acceptance, persistence, refresh APIs,
installation, runtime or UI. PostgreSQL models and migrations are unchanged.

This follows the producer's `catalogue/publication/consumer-handoff.md` and
`tools/publication_contract.py` as specification references only. Atlas imports
neither producer implementation nor producer configuration. The existing
[ADR 0011](../../decisions/0011-offline-official-provenance.md) pinned verifier,
roots and authority separation continue to apply; this does not approve a
publication authorization policy.

## Pointer structure

`parse_official_catalogue_selection(raw)` accepts literal `bytes` only, length
1–1,024 inclusive. It decodes strict UTF-8 and uses the pinned SDK strict JSON
parser. Duplicate keys (including escaped aliases), BOM/UTF-16/32, invalid JSON,
nonfinite numbers and unsupported shapes fail closed with safe diagnostic codes.
The object must contain exactly:

| Field | Required value |
| --- | --- |
| schema_version | Literal string `1.0` |
| sequence, release_id, asset_id | Literal positive integers, at most `2**53 - 1`; booleans, floats and strings rejected |
| release_tag | Exactly `catalogue-{sequence:06d}` |
| sha256 | Exactly 64 lowercase hexadecimal characters |
| previous_pointer_sha256 | Null for sequence 1; exactly 64 lowercase hexadecimal characters for later sequences |

The producer's canonical encoding must equal the **original bytes**:
`json.dumps(sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)` plus
one final newline, encoded as UTF-8. Alternate whitespace, key order, escapes
and numeric representations do not get normalized into accepted evidence.
The existing B1.1 safe integer bound is reused.

The result is a frozen, slotted `StructurallyValidSelection` containing immutable
scalar fields and a separate `source_bytes` snapshot. `pointer_sha256` hashes that
snapshot. Structural validity grants no authenticity, history or trust. There
is no pointer transition, high-water or acceptance implementation in this phase.

## Independent selection signature profile

`GithubSigstoreVerifier().verify_selection(original_bytes, bundle_bytes)` returns
the existing immutable `VerifiedProvenance` with profile
`official-catalogue-selection`. The fixed workflow is
`.github/workflows/catalogue-publish.yml@refs/heads/main`; subject is `current.json`.
The artifact bound is 1,024 bytes. Callers cannot override workflow, subject,
source ref, roots or verifier. Structure and signature remain separate checks.

The original catalogue (`catalogue.yml`) and package (`release.yml`) profiles
and their invocation rules remain unchanged. Selection reuses the exact-byte
SHA-256 binding, repository `benchristian88/atlas-connectors`, numeric repository
`1414494920` / owner `93822871`, GitHub Actions issuer, GitHub-hosted runner,
SLSA v1 and certificate/signer/configuration/dependency/builder consistency.
It uses the existing integrity-checked GitHub CLI **2.102.1**, frozen Public Good
roots, bounded output/deadline, isolated subprocess and verified transparency
timestamps. No online roots, token discovery or fallback is introduced.

The certificate and signed predicate must agree on an invocation exactly matching
`https://github.com/benchristian88/atlas-connectors/actions/runs/{positive_run_id}/attempts/1`.
Run IDs use 1–20 decimal digits without leading zeros. Other hosts, repositories,
attempts, missing attempts, suffixes and malformed run identities reject.
Authenticated evidence retains source commit, workflow/ref, invocation URI,
subject/digest, repository/owner, issuer/runner/predicate, log witnesses,
verifier/policy/root identities and verification time. It does **not** identify
the authorizing human or prove GitHub publication settings.

The [genuine frozen fixtures](../../../apps/api/tests/fixtures/official_catalogue/README.md)
verify offline. Selection source `8ce0b80c74d6ceb8ce75ac7ec8693f5bba78b305`
and original catalogue source `91dfd86f18d0b59ff977bb1e8a5fef42c5329943`
remain distinct. Historical signing source need not equal present main HEAD or
the later producer activation revision.

## Consumer-owned review schema

`parse_catalogue_trust_policy_candidate(raw, expected=None)` validates bounded
(1–8,192 byte), strict UTF-8/SDK JSON review input. It returns only a frozen,
slotted `CatalogueTrustPolicyReviewCandidate` with frozen nested values.
There is **no approved policy instance, default identity configuration, policy
loader, activation flag, authorization function or production trust-policy consumer**.
No environment variable, downloaded pointer/policy, release description or
provider response configures Atlas trust.

Every top-level field below is required; extras are rejected:

| Fields | Validation |
| --- | --- |
| schema_version | Literal string `1.0` |
| policy_id | Exactly `single-maintainer-v1`; explicit supported policy/mode, no inference or fallback |
| allowed_maintainer_id | Literal positive safe integer, distinct from publisher bot; never inferred from owner |
| repository_id, owner_id | Literal positive safe integers matching the independent provenance profile |
| publication_environment_id, package_environment_id | Literal positive safe integers |
| publisher_app_id, publisher_bot_user_id | Literal positive safe integers |
| publisher_app_slug | 1–100 lowercase ASCII letters/digits/hyphens, first character alphanumeric |
| reviewed_producer_revision | Exactly 40 lowercase hexadecimal characters |
| bootstrap | Exactly `sequence` (positive safe integer) and `pointer_sha256` (64 lowercase hex) |
| signing | Exactly `oidc_issuer`, `runner_environment`, `predicate_type`, `verifier_version`, `trust_root_id`, `trust_root_sha256` |

Signing requirements must exactly equal Atlas's independent existing issuer,
hosted runner, SLSA v1, pinned verifier and release-distribution root ID/digest.
Unavailable release pins reject validation. The optional explicit `expected`
review candidate constrains **all** values and rejects mismatches, including a
different maintainer. It does not activate either candidate. Test identities are
synthetic review fixtures, not copied producer policy or approved authority.

**Pending approval:** Atlas's final consumer security policy, actual maintainer,
environments, App/bot, reviewed producer revision and bootstrap pointer pins.
Successful schema validation does not satisfy that review.

## Boundaries and follow-up

The existing B1.3 `publication_not_immutable` and
`current_channel_policy_unavailable` rejection gates remain active. Selection
evidence also fails the existing catalogue-profile promotion check. No accepted
catalogue revision, package eligibility or executable authority is created.
The legacy remote Proxmox `0.2.0` package remains non-installable.

Phase 2A public observations are described below. Complete publication
authorization, immutable release selection and acceptance remain deferred.
Anonymous ruleset responses omit bypass actors: missing evidence must never mean
an empty bypass list. No privileged GitHub credentials or implicit authentication
fallback may be added to work around missing evidence.
Pointer history/recovery, transactional acceptance and remote installation remain
separate future work. Offline cryptographic verification satisfies none of those
authorization or operational acceptance requirements.

## Phase 2A public provider observations

`catalogue_publication_evidence.verify_public_observations(provenance, expected=..., reader=...)`
is an internal async evaluator. Callers supply genuine Phase 1
`VerifiedProvenance`, explicit `PublicObservationReviewExpectations` and an
operation-local `GithubReader`. Expectations contain the existing inactive review
candidate, a reviewed numeric publication workflow ID and five distinct reviewed
ruleset IDs (`RulesetReviewIdentities`). Phase 1 schema/release pins are rechecked;
neither producer responses nor producer configuration select expected authority.
There is no default configured identity, active policy loader or API integration.

The evaluator independently fetches and checks:

- Both latest run and attempt 1, using only the authenticated invocation. Numeric
  identity/attempt, manual main dispatch, authenticated SHA, public repository and
  head repository, exact API/HTML URLs, workflow ID/path and both human actors
  must agree. Latest attempt 2 rejects; original source need not equal current main.
- The public account routed by validated login, matching the externally supplied
  numeric maintainer, User type and every actor login. Ownership grants no authority.
- The independently retrieved active workflow, exact numeric identity/API/HTML
  URLs and `catalogue-publish.yml` path, consistent with Phase 1 signer evidence.
  Only bare path, path`@main` and path`@refs/heads/main` run forms are supported.
- Public repository/owner identities, protected main, and exactly one current
  `validate` check on the authenticated SHA, completed/successful from Actions
  App 15368. Missing, ambiguous, failed or conflicting checks reject.
- `catalogue-publication` environment ID/name, no admin bypass, protected-branch
  deployment policy, an explicit branch-policy protection rule and optional
  bounded wait timer. Required reviewers and unsupported rule types reject.
- Publisher App ID/slug/owner and exactly Contents Write plus Actions,
  Administration and Metadata Read. This is registration metadata only, not
  installation/token scope or historical permissions.
- The complete bounded five-ruleset inventory and each pinned detail: repository
  source, active enforcement, exact ref scopes and required visible protections.
  Main requires zero approving reviews, stale-review dismissal, no last-push
  approval and strict Actions `validate` checks. Current/history/bootstrap locks
  and publication tags retain their explicit creation/update/deletion/force-push
  protections; an additional tag non-fast-forward lock is supported. Returned
  bypass arrays must match the expected no-bypass or Publisher Integration-only
  profile; a withheld field stays unavailable.

`GithubReader.publication_metadata` reuses the existing anonymous transport.
It accepts only fixed repository endpoints or strictly validated decimal ID,
40-character source SHA, account login and App slug components. It accepts no
remote URL. Every response is at most 256 KiB, strict UTF-8/unambiguous JSON;
metadata redirects and any pagination Link fail closed. The check list requests
two slots and requires exactly one; the ruleset list requests six slots and
requires exactly five. No continuation URL is followed. Existing DNS, HTTPS,
5/5/15-second connect/read/request timeouts, shared 90-second operation deadline,
sanitized errors/retries/rate limits and disabled ambient auth/proxy/cookies apply.

The frozen, slotted `VerifiedPublicObservations` retains the genuine provenance,
review expectations, observation start/end, both checked run records (including
repository/head repository and actors), account, workflow, current main SHA,
source CI, environment, App and ordered rulesets. All nested results are frozen
values/tuples; checked visible rule parameters are immutable canonical JSON bytes.
`bypass_actors=None` means withheld; `()` means an explicitly returned empty
array. Neither is inferred from the other. Results are operation-local and are
not persisted or exposed through a route.

Every result carries `reviewed_ruleset_evidence_required` and
`consumer_trust_approval_required` as non-constructor authorization blockers,
including when public bypass arrays happen to be returned. This type is neither
a publication-authorized candidate nor package verification evidence. A successful
public evaluation cannot open B1.3's gates, approve consumer trust, renew catalogue
currentness, promote catalogue data or make Proxmox 0.2.0 installable.

[Proposed ADR 0012](../../decisions/0012-official-catalogue-publication-authorization.md)
records the actual one-day producer preflight retention and missing immutable
archive/binding contract. It recommends preserved S4-authenticated historical
ruleset evidence as a future amendment while continuing rejection today. That
recommendation is not approved or implemented. Current public settings cannot
prove uninterrupted historical settings or detect hidden present-day bypass changes.
