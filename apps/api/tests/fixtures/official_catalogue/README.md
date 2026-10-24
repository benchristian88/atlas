# Frozen sequence-1 publication fixture

`catalogue-000001.json` is an exact copy of the published sequence-1 release
asset. Both assets were independently downloaded over HTTPS for B1.1 and
compared byte for byte; `publication.json` records their expected identities.
One JSON fixture represents both aliases without duplicating identical content
within this repository. Each repository retains a copy for independent CI.

Source: [official catalogue v1 release](https://github.com/benchristian88/atlas-connectors/releases/tag/catalogue-v1).
Publication source commit: `91dfd86f18d0b59ff977bb1e8a5fef42c5329943`.
Schema `1.0`, sequence `1`, generated at `2026-10-18T16:04:26Z`, one active
Proxmox `0.2.0` entry, exactly **10,585 bytes**.
SHA-256: `55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd`.

Tests read these files offline and validate the complete contract and entry
size. They never fetch or execute a Connector. Do not regenerate this fixture
using the current repository HEAD, rebuild sequence 1, or replace the release.
Add a separately named fixture for any future publication.

The digest and equality checks establish byte identity and compatibility only.
They do not by themselves authenticate a publisher or make an entry eligible
for installation. The separate B1.2 verification tests below authenticate the
original artifact bytes.

## B1.2 frozen genuine attestations

Captured 21 October 2026 through the public GitHub digest-attestation API for
benchristian88/atlas-connectors. The response contained public Sigstore v0.3
bundles; duplicate catalogue references identified the same attestation 57152061
and were deduplicated by exact bundle content. Only the bundle is retained,
serialized with sorted keys and a terminal newline; signed payload, certificate,
signature and transparency evidence remain unchanged. API envelopes and
temporary signed download URLs are deliberately excluded. Inspection found only
public workflow/source identities, certificates, signatures and log proofs; no
credentials, customer inventory or executable package bytes.

| Fixture | SHA-256 | Expected signed artifact |
| --- | --- | --- |
| catalogue.sigstore.json | 0a404de77a6c47dc2f08e3acecf835a01313e924f6883a4b13d720c57610f72f | catalogue.json and catalogue-000001.json, digest above |
| package.sigstore.json | 2929b38721e31d48ca9ee8a51753c595880dca3c5fef9dea79c8bfdf0dca7db4 | proxmox-0.2.0.tar.gz, a14fec5ab485c980688ff5907e8835ddd3e9cecd1a6989ef252cbcb1b1dc4ef8 |

Catalogue certificate: .github/workflows/catalogue.yml at refs/heads/main,
source 91dfd86f18d0b59ff977bb1e8a5fef42c5329943, Rekor witness
2026-10-18T16:07:56Z. Package certificate: .github/workflows/release.yml at
refs/tags/proxmox-v0.2.0, source 456a5bfdd1398c19da9ffef29216029027e24278,
Rekor witness 2026-10-18T06:51:38Z. Both authenticate repository ID 1414494920,
owner ID 93822871, GitHub Actions issuer and github-hosted runner.

[Policy/deployment](../../../../../docs/deployment/attestation-verification.md)
records the independently pinned roots/verifier and certificate-versus-predicate
boundary. Real catalogue verification is mandatory in normal CI. Package evidence
is used for negative cases; a separately acquired package is checked through
infra/ci/verify-official-fixtures.py for opt-in real package acceptance without
installation/execution. No live GitHub access is needed by ordinary tests.

Both GitHub releases remained mutable when captured. These attestations prove
workflow provenance, not immutable release history, asset IDs or release approval.

## Phase 1 frozen genuine selection

Captured anonymously over HTTPS on 25 October 2026 (Pacific/Auckland) from the
exact historical root `a1597730687be993d766ddb465a0d3362aef2d02`:

- [current.json](https://raw.githubusercontent.com/benchristian88/atlas-connectors/a1597730687be993d766ddb465a0d3362aef2d02/current.json)
- [current.sigstore.json](https://raw.githubusercontent.com/benchristian88/atlas-connectors/a1597730687be993d766ddb465a0d3362aef2d02/current.sigstore.json)

Both fixtures retain exact original bytes, including formatting and final newline;
the bundle was not reserialized. The pointer's independently supplied SHA-256 was
checked **before** creating fixtures. The actual pinned Atlas verifier then
authenticated the pointer/bundle before they were copied into this directory.

| Fixture | Bytes | SHA-256 |
| --- | ---: | --- |
| current.json | 251 | a275f63d0ac818a193826478328ee324be62353addc5c97a2ed0a28d217b5372 |
| current.sigstore.json | 11,781 | 5ccab9abdc31fbae55787c102e4f2eb305f7d37966d9dacb02d0c5cb8f8cf522 |

The pointer selects release `421426993`, tag `catalogue-000001`, catalogue asset
`667867351` and the unchanged catalogue digest above. No new catalogue or package
bytes were generated or acquired. Inspection found only public identities,
certificates, signatures, payload and transparency evidence; no credentials,
inventory or executable content.

Genuine offline verification authenticates workflow
`.github/workflows/catalogue-publish.yml@refs/heads/main`, signing source
`8ce0b80c74d6ceb8ce75ac7ec8693f5bba78b305`, invocation
`https://github.com/benchristian88/atlas-connectors/actions/runs/39896288128/attempts/1`
and Rekor witness `2026-10-23T03:41:42Z`. This signing source differs from the
original catalogue build source `91dfd86f18d0b59ff977bb1e8a5fef42c5329943` and
producer activation revision `51f8693fbcca1e4c6c9615662bca368839ea0757`.
Neither present main HEAD nor the activation receipt supplies signing identity.

`test_official_selection_provenance.py` requires real GitHub CLI 2.102.1 and
Atlas's frozen Public Good roots. Separate structured-output policy tests are
explicitly labelled and cannot substitute for genuine verification. Ordinary
tests need no network or credentials. These fixtures prove selection provenance
only: consumer trust approval, provider authorization, history acceptance and
remote installation remain unavailable. Proxmox `0.2.0` remains non-installable.
