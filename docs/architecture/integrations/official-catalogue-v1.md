# Official Connector Catalogue v1: B1.1 structural boundary

**B1.3 integration:** the unchanged parser now feeds the separate
[bounded consumer and durable trust service](../../deployment/official-catalogue.md).
That service adds global status/refresh APIs and migration `20261021_0031`.
Genuine live verification succeeds, but promotion remains closed pending the
[publication prerequisites](b1-3-publication-plan.md). Statements below about no
I/O, migration or API authority describe this B1.1 parser itself.

Separate [selection Phases 1/2A/2B](official-catalogue-selection.md) authenticate
the historical pointer, evaluate public observations and implement a restricted
original-sequence-one bootstrap authorization exception. Its policy proposal is
inactive pending complete consumer pin approval. The exception tolerates only
missing historical bypass arrays; it supplies no immutable selection, trusted
revision or executable eligibility. These components do not change this parser
or B1.3 promotion. The limited owner decision and remaining approvals are recorded
in [Proposed ADR 0012](../../decisions/0012-official-catalogue-publication-authorization.md).

B1.1 implements the offline `parse_official_catalogue(bytes)` service in
`apps/api/app/services/official_catalogue.py`. It accepts untrusted aggregate
catalogue bytes and returns `StructurallyValidCatalogue` or a typed
`OfficialCatalogueError` with a stable diagnostic code. It performs no network
access, database access, filesystem writes, installation or activation.

This implements the structural portion of [ADR 0006](../../decisions/0006-verified-connector-supply-chain.md).
It does not authenticate a publisher or implement the remote catalogue journey.
The SDK remains pinned at 1.1.0 in both repositories; no new SDK release or
runtime dependency on an `atlas-connectors` checkout is needed.

## Exact envelopes

The aggregate has exactly these six fields; missing or additional fields fail:

| Field | Rule |
| --- | --- |
| `schema_version` | String exactly `1.0` |
| `sequence` | Literal JSON integer, 1 through 9007199254740991 inclusive |
| `generated_at` | Valid calendar timestamp, exactly `YYYY-MM-DDTHH:MM:SSZ` |
| `publisher_id` | String exactly `atlas-official` |
| `repository` | String exactly `benchristian88/atlas-connectors` |
| `entries` | Array of 0 through 200 entries inclusive |

Each entry has exactly `status`, `release_tag`, `release_asset_id` and `manifest`.
Status is `active` or `withdrawn`. The release asset ID is a positive literal JSON
integer within the same safe range as sequence. Booleans, floats and strings do
not satisfy either integer field. Entries must already be lexically sorted by
`(manifest.id, manifest.version)`. Connector/version pairs and release asset IDs
must each be unique. The consumer never sorts or repairs input. Lexical ordering
is a serialization rule, not version precedence; future update selection must
use semantic version comparison.

The complete combined Manifest uses the pinned SDK's canonical validator,
including its required compatibility declarations and supported Manifest
versions. Aggregate schema version `1.0` does not force Manifest version `1.0`.
Official distribution additionally requires:

- Publisher and provenance publisher `atlas-official`, repository
  `benchristian88/atlas-connectors`.
- Tag `<manifest.id>-v<manifest.version>` and asset URI
  `https://github.com/benchristian88/atlas-connectors/releases/download/<tag>/<manifest.id>-<manifest.version>.tar.gz`.
- Digest `sha256:` followed by exactly 64 lowercase hexadecimal characters.
- Provenance method `github-artifact-attestation-sigstore`, package workflow
  `.github/workflows/release.yml`, and a 40-character lowercase hex source commit.
- Evidence URI `https://github.com/benchristian88/atlas-connectors/attestations`.

These are declarations only. The catalogue signer workflow is separately
`.github/workflows/catalogue.yml`; [B1.2 provenance verification](../../deployment/attestation-verification.md)
authenticates each identity against its respective attestation. `publisher_id` and provenance metadata are never
proof of identity.

## Strict parsing and resource limits

Only bytes are accepted. The raw size is checked before decoding. UTF-8 is
mandatory; BOM, malformed UTF-8/JSON, duplicate keys (including escaped aliases),
non-finite numbers and inappropriate root structures fail closed. Integers
anywhere in the document must remain within the producer's JSON-safe range.
Excessive nesting is rejected by an escape-aware scan before JSON decoding:
at most 32 simultaneously open object/array containers, well above the
non-recursive v1 schema's needs. SDK/schema/encoding errors become typed safe
diagnostics without reflecting untrusted values.

All three inclusive contract limits apply independently:

| Measurement | Maximum |
| --- | --- |
| Original received bytes | 4,194,304 bytes (4 MiB) |
| Canonical complete aggregate | 4,194,304 bytes (4 MiB) |
| Each canonical standalone entry | 262,144 bytes (256 KiB) |
| Entry count | 200 |

Canonical measurement is exactly the producer's calculation:
`(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")`.
The entry value is the complete four-field envelope including its Manifest,
serialized at root indentation, with all whitespace and one terminal newline.
Indentation from placement inside the aggregate array is excluded from the entry
measurement but included in aggregate measurement. UTF-8 bytes, not characters,
are counted. Atlas counts encoder chunks and stops at the limit to avoid
allocating an expanded whole canonical document.

The producer now applies this entry limit in `validate_entry`, including calls
through aggregate object validation. Its existing independent 256 KiB raw
registry-file limit is retained. Compact JSON cannot evade canonical sizing;
extra raw whitespace cannot evade raw sizing. Tests pin the same calculations
and real limits independently in each repository.

## Trust, bootstrap and future consumer responsibilities

The result retains the original `source_bytes` for future digest/attestation
verification. Its `document` is ordinary caller-owned metadata, not verification
evidence or an installable `CataloguePackage`. Mutating that dictionary cannot
authenticate it or change the original bytes. Future verification must bind
trusted results to the original received bytes, not reserialized JSON.

The existing bootstrap catalogue has exactly `catalogue_version`,
`release_identity` and `entries`. Its release-packaged digest and bundle allowlist
remain separate. B1.1 does not replace its schema, register remote entries in its
provider, or connect structural results to an API/installer. B1.2 adds separate `verify_catalogue` and `verify_package` methods returning
`VerifiedProvenance`. The legacy remote installation adapter still fails closed
with `missing_attestation`; no remote install eligibility adapter exists.
Missing/corrupt verification dependencies fail closed. Existing global-admin authorization,
customer/site scope, installed-package records, credentials, mappings and runtime
execution are unchanged. No migrations or frontend/API changes are required.

There is no `expires_at`: unchanged catalogue state needs no periodic
republication. `generated_at` is audit metadata, not a trusted freshness clock.
Future consumers must retain the highest authenticated sequence, reject rollback,
and define unchanged-sequence confirmation. Daily refresh and a 72-hour local
authenticated-refresh gate for remote install/update belong to B2. Bundled and
already-installed packages must remain usable offline. B1.1 enforces no freshness
or update-selection policy.

## Frozen publication compatibility

The [sequence-1 fixture](../../../apps/api/tests/fixtures/official_catalogue/README.md)
preserves the published bytes of both `catalogue.json` and `catalogue-000001.json`:
10,585 bytes, SHA-256
`55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd`.
It contains one active Proxmox 0.2.0 entry and passes the new standalone entry
limit. Both assets were independently downloaded and compared during fixture
capture; normal tests are offline. Each repository carries one frozen copy plus
the two expected asset identities for independent CI. Byte equality demonstrates
compatibility; the separate B1.2 tests now cryptographically authenticate the
original bytes with the frozen genuine bundle. Build provenance does not prove
GitHub release immutability. Sequence 1 was not rebuilt or
republished, and no Proxmox package was installed or executed.
