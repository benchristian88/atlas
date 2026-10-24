# Official catalogue selection — Phase 1

Implemented internal components: strict pointer parsing, a separate offline
selection provenance profile and consumer-policy **review schema**. These extend
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
loader, activation flag, authorization function or runtime consumer**.
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

Provider run/attempt, actor, workflow, source CI, environment, App, immutable
release and ruleset authorization are deferred to the next explicitly reviewed
phase. Anonymous ruleset responses omit bypass actors: missing evidence must
never mean an empty bypass list. No privileged GitHub credentials or implicit
authentication fallback may be added to work around missing evidence.
Pointer history/recovery, transactional acceptance and remote installation remain
separate future work. Offline cryptographic verification satisfies none of those
authorization or operational acceptance requirements.
