# Official catalogue retrieval and durable trust (B1.3)

B1.3 provides bounded retrieval, genuine B1.2 verification, PostgreSQL trust
storage, sequence/history checks and global manual-refresh APIs. **Production
promotion remains blocked:** the established channel does not provide immutable
history plus independently established publication approval and a separately
advancing current pointer. This is a delivered foundation, not full milestone
acceptance. No remote package download, installation, activation, automatic update
or new UI is enabled. Bundled and installed connectors remain independent.

[Selection Phase 1](../architecture/integrations/official-catalogue-selection.md)
now strictly parses and genuinely verifies the published historical selection
offline, using a distinct signature profile. Its consumer trust-policy schema
produces review candidates only; final Atlas security approval and provider
authorization are pending. This internal work does not change this B1.3 adapter,
its endpoints, publication gates or trusted PostgreSQL state.

## Fixed source and publication boundary

The consumer's release-owned policy is in `catalogue_source.py`; no browser or
environment setting selects a URL, repository, signer, root, tag or file path.
It reads only public resources, without a GitHub token:

- `GET https://api.github.com/repos/benchristian88/atlas-connectors` verifies
  numeric repository **1414494920**, owner **93822871** and exact repository name.
- `GET .../releases/tags/catalogue-v1` resolves the established channel, pinned to
  release **416561696**, exact API/HTML URLs, non-draft/non-prerelease state.
- `GET .../releases/assets/{id}` with `Accept: application/octet-stream` retrieves
  `catalogue.json` and its matching `catalogue-{sequence:06d}.json`. Asset IDs come
  from that release's metadata; name, URL, size, state and digest must agree.
- `GET .../attestations/sha256:{original-byte-digest}?per_page=4` retrieves embedded
  bundles; neither returned bundle URLs nor pagination links are followed.
- Repository and channel metadata are reread after verification. Release identity,
  publication/update metadata and both asset identities must remain unchanged.
  Volatile download counts do not participate in equality.

The repository-wide latest-release endpoint is never used. Connector and
catalogue releases coexist. Catalogue sequences and connector identities remain
data-driven. The frozen first sequence/digest is a bootstrap floor and exact
sequence-1 identity, not a permanent current-version pin. Higher first sequences
must pass the same complete trust pipeline, including the future publication gate.

These operations follow GitHub's [release API](https://docs.github.com/en/rest/releases/releases),
[binary asset API](https://docs.github.com/en/rest/releases/assets#get-a-release-asset)
and [artifact-attestation API](https://docs.github.com/en/rest/repos/attestations).
The GitHub API can redirect binary retrieval; metadata redirects are rejected.

The live check on **21 October 2026** found `immutable: false`. Both catalogue
assets still matched SHA-256
`55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd`.
The connector workflow prepares and attests candidates; it does not publish
releases. Naming an Actions environment does not prove reviewer settings or
release approval. A build signature cannot supply those missing guarantees.

`require_publication` rejects mutable releases as `publication_not_immutable`.
Even setting this same release immutable yields
`current_channel_policy_unavailable`: freezing it also freezes its current alias.
There is no runtime bypass or permissive test mode. The separate
[publication implementation plan](../architecture/integrations/b1-3-publication-plan.md)
must precede a reviewed Atlas publication adapter. No hypothetical URL is used.

## Transport and verifier limits

| Resource | Limit / policy |
| --- | --- |
| Catalogue original bytes | 4 MiB, plus unchanged B1.1 canonical/envelope bounds |
| Repository/release metadata | 256 KiB per response; at most 100 release asset records |
| Attestation response | 1 MiB total; at most three embedded bundles; a fourth fails closed |
| Single bundle / verifier output | Existing B1.2 1 MiB limits |
| Connections | One operation-local session, connector concurrency two |
| Connect / read / request | 5 / 5 / 15 seconds |
| Refresh retrieval budget | 90 seconds shared across requests/verification; reserve the complete B1.2 20-second subprocess budget before each verification |
| Redirect | At most one binary API 302 to `release-assets.githubusercontent.com` |
| Retry | At most one retry after 250 ms for transient connections or HTTP 500/502/503/504 without a server delay; TLS/other protocol failures are not retried |
| Coalescing / cooldown | One durable 150-second lease; 15-minute instance-global cooldown |
| Rate-limit delay | Honor Retry-After/date/reset through durable next-attempt time; pathological values capped at one day |

TLS certificate verification is enabled. Only HTTPS, the exact API/distribution
hosts and default/443 ports are admitted. Userinfo, fragments, backslashes,
control characters, unexpected origins and private/non-global DNS answers fail.
DNS validation occurs in the connector's resolver used for the connection; no
separate unchecked second lookup is made. Corporate proxies, ambient credentials,
cookies and decompression are disabled. `Accept-Encoding: identity` is sent;
encoded bodies are rejected. Both declared length and streamed bytes are bounded.
A truncated response fails. Rate limits do not cause request-thread sleeps.

Manual refresh executes synchronously in FastAPI's request thread pool. The
verifier remains in the API distribution, with no event-loop blocking, new worker,
queue, broker or scheduler. The existing worker owns discovery operations, not
this verifier. Shutdown/crash may leave a lease until its bounded expiry.

## Cryptographic and publication evidence

The pipeline reuses `parse_official_catalogue` unchanged and
`GithubSigstoreVerifier().verify_catalogue(original_bytes, bundle,
subject_name="catalogue.json")`. It requires the catalogue profile, not the
executable-package profile. B1.2 verifies exact original-byte digest, signature,
Public Good chain/log evidence, numeric repository/owner identity, hosted runner,
issuer and `.github/workflows/catalogue.yml@refs/heads/main` identity/ref/source
consistency. Its pinned CLI, roots and failure semantics are unchanged.

Snapshot bytes must equal authenticated current bytes. They are consistency
checks only; this existing mutable snapshot is not claimed to be immutable.
A successful channel reread alone cannot renew currentness. Publication policy,
sequence/history checks and commit must also succeed.

Accepted revisions retain original bytes, SHA-256, schema/sequence, generated time,
acceptance time, bounded typed verified claims (including verifier/policy/root
identity) and safe release/asset identities. Raw CLI output, signed download URLs,
raw attestation bundles and credentials are not persisted. Failed candidates are
not stored as accepted revisions; download/authentication times can still record
completed stages without granting trust.

## Transactions, history and restore

Migration `20261021_0031` adds two instance-global tables. It changes no customer,
site, integration, credential, bootstrap or installed-package record and performs
no network I/O. `connector_catalogue_revisions` is append-only: PostgreSQL rejects
UPDATE/DELETE. `connector_catalogue_state` contains the highest sequence/digest,
composite FK to its revision, stage timestamps, conflict/error, lease and cooldown.
PostgreSQL rejects checkpoint deletion/decrease/same-sequence identity changes.

A short transaction takes the existing advisory-lock pattern plus a row lock,
records an operation UUID and commits. Network and cryptography run without
PostgreSQL row locks. Finalization reacquires the lock, checks UUID and lease
expiry against committed state, reapplies history checks, inserts revision and
updates state/audit atomically. A lost lease cannot finalize. Persistence or audit
failure rolls back promotion and leaves the old accepted catalogue intact; the
claim expires for recovery. Lock/statement waits are bounded to 3/10 seconds.

| Candidate transition | Result |
| --- | --- |
| First | Full trust gates; sequence at least one, exact frozen digest if sequence one |
| Same sequence / identical bytes | No duplicate revision; live authoritative full verification required to renew currentness |
| Higher sequence | Full trust gates and consistent immutable historical identities |
| Lower sequence | `catalogue_rollback`; old state/currentness preserved |
| Same sequence / changed bytes | `catalogue_substitution`; source conflict, old state preserved |
| Invalid provenance/structure/publication | Rejected; stage diagnostics only, no trust advancement |

The state holds a derived identity-history index for every observed ID/version:
SHA-256 of canonical complete Manifest + release tag + asset ID, and retained
withdrawal status. Omission does not erase identity or withdrawal. A withdrawn
version cannot reactivate; package absence does not uninstall/revoke anything.
Compatibility with this Atlas/runtime is a later eligibility question, not
catalogue corruption. History is bounded to 10,000 identities/approximately
2 MiB; exhaustion fails closed without dropping history.

A missing/older checkpoint can reconstruct from retained revisions (up to 1,000
revisions per recovery), verifying their byte digests and historical consistency;
recovery streams one revision at a time with a 20-second processing budget,
clears currentness and never invents a live confirmation. Retained
history beyond that exceptional recovery bound requires operator review.
The normal refresh reads the cumulative bounded history, not every prior blob.

The existing `normal_operation` shared filesystem lock spans the entire refresh.
A restore must drain it before replacing PostgreSQL; finalization also checks the
maintenance marker. A restored lease cannot let an old process promote across
replacement. The complete trust tables are included in ordinary database backups.
**Restoring the entire database can restore an older trust checkpoint.** Absolute
rollback resistance needs a checkpoint outside that rollback boundary; no external
witness is added in B1.3. See [backup/restore](backup-restore.md).

## API and troubleshooting

| Route | Required global authority | Contract |
| --- | --- | --- |
| `GET /api/integration-catalogue/status` | `integration_runtime.view` | Sanitized persisted status plus read-only accepted entries |
| `POST /api/integration-catalogue/refresh` | `integration_runtime.manage` | No body or `{}`; no query parameters; bounded coalesced operation |

Scoped integration managers cannot refresh or inspect global runtime status.
The static routes precede the connector-ID route. Existing list/detail, bootstrap
installation and UI response contracts remain unchanged. Read-only remote entries
have `package_available: false` and no supported actions; they never enter the
existing installer selection provider. Existing authentication, origin checks
and no-store response policy apply.

Refresh results are `accepted`, `unchanged`, `in_progress`, `cooldown` or `failed`.
Ordinary failures use HTTP 200 with the explicit result and persisted diagnostic;
authentication/authorization and invalid input retain 401/403/422. Restore mode
uses the existing HTTP 503 mechanism. Failed persistence/ownership may return a
safe top-level `code` because no new state could be committed.

`generated_at` describes the source build. `last_attempt_at`, `last_download_at`,
`last_authenticity_verified_at`, `last_confirmed_current_at` and `accepted_at` are
separate. No `expires_at` exists. Old generated bytes can be current if the live
authoritative channel is fully verified and accepted. Cached verification,
historical snapshot retrieval and failed/newer-unusable candidates cannot renew
currentness. The previous timestamp remains historical evidence, not a claim
that the most recent attempt succeeded. Persistent `source_conflict` is cleared
only by successful full acceptance. B2 must consult conflicts as well as age.

| Diagnostic group | Operator response |
| --- | --- |
| `publication_not_immutable`, `current_channel_policy_unavailable` | Expected present blocker; implement/audit publication plan, then ship a reviewed Atlas policy. Do not disable gates. |
| `source_rate_limited`, `source_forbidden`, `source_not_found`, `source_unavailable`, `source_timeout` | Respect `next_attempt_at`; check public connectivity/repository availability. A token is not required or accepted. |
| `source_tls_failed` | Check certificate validation and network interception; do not disable TLS verification. |
| `invalid_source_*`, `unexpected_source_response`, `truncated_source_response`, `source_response_too_large` | Source/transport violates fixed bounds or identity. Preserve diagnostics; investigate rather than override. |
| `invalid_channel_identity`, `invalid_asset_identity`, missing/ambiguous asset, `asset_digest_mismatch`, `channel_changed`, `historical_snapshot_mismatch` | Publication inconsistency; do not promote. |
| B1.1/B1.2 diagnostic codes | Consult the structural and [provenance](attestation-verification.md) contract; repair packaged dependencies through normal upgrades. |
| `catalogue_rollback`, `catalogue_substitution`, `historical_identity_changed`, `withdrawal_reactivated` | Security conflict; preserve last-known-good/history and investigate publication. |
| `refresh_ownership_lost`, `catalogue_persistence_failed`, `catalogue_state_unavailable` | Wait for lease/cooldown, check database health/maintenance; no candidate was promoted. |
| `history_capacity_exceeded`, `history_recovery_limit`, `checkpoint_inconsistent` | Operator review of retained trust history; never delete history to force acceptance. |
| `catalogue_refresh_internal_failure` | Safe unexpected failure; no raw exception/body is exposed. Review deployed code/dependencies. |

## Validation and next increments

Ordinary CI uses controlled HTTP responses and disposable PostgreSQL. Genuine
pipeline tests invoke the actual pinned verifier. Hypothetical future connectors
are tested through structural parsing, projection and private storage primitives
with explicitly unauthenticated storage fixtures. Those tests are not signatures
and are never supplied to a production verifier-success path.

Opt-in live acceptance, from `apps/api`, with `ATLAS_TEST_DATABASE_URL` set to an
**empty disposable** `atlas_b13_*` or `atlas_test_*` database and a separate private
`ATLAS_STATE_DIR`:

```bash
python -m scripts.accept_official_catalogue --allow-live-github --disposable-database
```

The script migrates the empty database, fetches/verifies authentic public bytes,
reopens the session, then simulates unavailability. It prints `milestone_accepted`
and distinguishes zero accepted revisions from live last-known-good recovery.
The present expected result is cryptographic success and publication rejection.
It never downloads or activates packages.

B2 still needs daily scheduling, authoritative <72-hour installation eligibility,
compatibility/version/withdrawal lifecycle projection and UI integration. B3 still
needs approved immutable package publication, verified package bytes bound to an
accepted current catalogue, archive/store gates and explicit global administrator
approval. B4 must prove newly published compatible connectors appear without an
Atlas rebuild. These increments are not implemented here.
