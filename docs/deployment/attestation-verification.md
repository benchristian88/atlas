# Official artifact provenance verification (B1.2)

B1.2 implements offline cryptographic verification of supplied catalogue and
connector-package bytes. It does not retrieve catalogues, download connector
packages, persist trusted state, install packages or expose new API/UI routes.
[ADR 0011](../decisions/0011-offline-official-provenance.md) refines the existing
supply-chain boundary. The SDK and B1.1 structural parser are unchanged.

The separate [selection Phase 1 component](../architecture/integrations/official-catalogue-selection.md)
adds `verify_selection(original_bytes, local_bundle_bytes)` with profile
`official-catalogue-selection`, fixed `catalogue-publish.yml@refs/heads/main`
and subject `current.json`. It reuses this pinned offline infrastructure, requires
an exact first-attempt invocation and preserves the catalogue/package profiles.
Its strict pointer parser and consumer-policy review schema grant no publication
authorization or acceptance; B1.3 rejection remains active.

## Interface and authority

Use the existing import boundary:

~~~python
from app.services.connector_verification import GithubSigstoreVerifier
from app.services.official_provenance import PackageArtifactContext
from app.services.official_catalogue import parse_official_catalogue

structural = parse_official_catalogue(original_bytes)
evidence = GithubSigstoreVerifier().verify_catalogue(
    structural.source_bytes, local_bundle_bytes, subject_name="catalogue.json"
)
# evidence is VerifiedProvenance, never an installable catalogue/package.

package_evidence = GithubSigstoreVerifier().verify_package(
    original_package_bytes,
    local_package_bundle_bytes,
    PackageArtifactContext(connector_id, version, expected_sha256, expected_source_commit),
)
~~~

The expected package SHA-256 is 64 lowercase hexadecimal characters, without the
sha256 prefix. Context is an expectation to check, not authenticated evidence.
B3 must obtain it from durably accepted metadata and apply publication,
freshness, withdrawal, compatibility, qualification, administrator authorization
and protected-store controls separately. No connector IDs or versions are
allowlisted in the production verifier.

Phase 4B.12A adds a separate [local release acceptance adapter](local-release-acceptance.md)
for exact officially signed immutable releases outside catalogue selection. It
reuses this unchanged `verify_package` profile, with independently checked release,
tag, asset and source expectations. Protected root operator authorization remains
distinct from provenance and catalogue eligibility; no verifier/root override exists.

Catalogue names may be catalogue.json or a numbered catalogue snapshot.
Package names and tag refs derive from validated generic ID/SemVer context.
Input bytes remain the digest authority, including whitespace. Never authenticate
a reserialized dictionary or reuse evidence for different bytes.

VerifiedProvenance includes the selected profile, exact SHA-256 and subject
name, certificate-authenticated repository/owner IDs, repository/workflow
identity, source ref/commit, issuer, runner, invocation URI, signed predicate
type, verified log timestamps, verifier/policy/root versions and local verification
time. Local verification time is not publication freshness. Subject/predicate
claims are authenticated statements made by the workflow, not proof of release
approval or independent build correctness.

The old verify(archive, package) installation adapter still checks the expected
digest and rejects missing local provenance with missing_attestation. It cannot
turn a manifest claim into installation evidence. Existing bootstrap release
allowlists, qualification, store validation, mappings, scoped connections and
runtime authorization are unchanged.

## Policy v1

| Claim | Catalogue | Executable package |
| --- | --- | --- |
| Repository | benchristian88/atlas-connectors | Same |
| Numeric repository / owner | 1414494920 / 93822871 | Same |
| Workflow | .github/workflows/catalogue.yml | .github/workflows/release.yml |
| Source ref | refs/heads/main | refs/tags/{connector_id}-v{version} |
| Source commit | Certificate's 40-character commit, consistent with build signer/configuration and signed dependency | Same, additionally equal to expected accepted source commit |
| OIDC issuer | https://token.actions.githubusercontent.com | Same |
| Runner | github-hosted only | Same |
| Predicate | https://slsa.dev/provenance/v1 | Same |

Repository IDs were independently checked using the public GitHub repository API
on 21 October 2026 and confirmed in cryptographically verified certificates.
Untrusted catalogue repository IDs are never an authority. Required missing
certificate extensions fail closed. SAN, buildSignerURI and buildConfigURI must
all identify the exact selected workflow/ref; their commits must agree. This
initial policy deliberately does not admit reusable workflows.

The verifier checks SLSA workflow/source/builder/invocation assertions against the
certificate. Predicate internalParameters do not substitute for certificate
identity. Workflow compromise can still cause signed false build assertions.

## Cryptographic chain and offline subprocess

The fixed executable uses gh attestation verify with a local bundle, local
custom trusted root, exact certificate identity, explicit issuer/repository/ref,
SLSA predicate, SHA-256 and deny-self-hosted-runners. Package verification also
sets source/signer digests. Successful JSON output is then checked for stronger
numeric identity and claim consistency. Nonzero exit can never produce evidence.

The packaged Public Good root selects sigstore-go's certificate-chain,
signed certificate timestamp, transparency-log and observer-timestamp checks.
Only Public Good Fulcio/Rekor material is included; GitHub's separate private
instance/TSA roots are deliberately excluded. Both genuine fixtures use Public
Good provenance. Missing log evidence fails; no skip-inclusion or online fallback
is enabled.

Reviewed pinned source:
[verification implementation](https://github.com/cli/cli/blob/v2.102.1/pkg/cmd/attestation/verification/sigstore.go),
[certificate checks](https://github.com/cli/cli/blob/v2.102.1/pkg/cmd/attestation/verification/extensions.go),
[CLI contract](https://cli.github.com/manual/gh_attestation_verify).
With local artifacts/bundles and custom roots this path performs no network
lookup. GitHub enterprise/OCI paths are not passed to it.

Each call uses an absolute integrity-checked executable, an argument array,
no shell, closed inherited descriptors, no stdin, and a newly constructed
environment. HOME/config/cache/TMPDIR point inside a private 0700 workspace.
No GitHub tokens, application credentials, proxy configuration, debug flags,
dynamic-loader variables or user CLI configuration are inherited.
Artifact/bundle/root files use 0600 and fixed local names. The process group is
killed and reaped on failure; temporary files are removed on all handled exits.
Supported deployments must retain an executable application filesystem; temporary
storage can be noexec.

Limits are 4 MiB catalogue / 20 MiB package, 1 MiB single v0.3 Sigstore bundle,
128 KiB roots, 64 MiB verifier binary, 1 MiB combined stdout/stderr and a shared
20-second subprocess deadline including the version check. Inputs are bounded
before subprocess launch. The call is synchronous; future async callers should
use a bounded execution context rather than block an event loop.

ProvenanceError has a stable reason enum and safe code only; no raw stderr,
certificate input, bundle, filesystem exception or subprocess command is logged.
The enum distinguishes missing/malformed/oversized inputs, unavailable/version
dependencies, roots, identity/context failures, timeout/output bounds and
internal failure. gh does not supply stable structured cryptographic errors:
nonzero verification exits conservatively return unverifiable_provenance.
The reserved invalid_signature category is not guessed from stderr. A precise
wrong_repository/workflow/ref/digest/predicate/runner error is only emitted when
Atlas can establish it from its own checks; otherwise use the conservative code.

## Verifier distribution and bootstrap

[distribution.json](../../apps/api/app/attestation/distribution.json) is the
single platform lock for GitHub CLI **2.102.1**, released 20 October 2026.
The origin is [cli/cli v2.102.1](https://github.com/cli/cli/releases/tag/v2.102.1),
an immutable GitHub release when inspected. Archives are not committed.

| Platform | Archive SHA-256 |
| --- | --- |
| Linux amd64 | 77b9e297e94c50336823d0f84de7ef1be60cba704601fa0d98f129f47a94987b |
| Linux arm64 | 5019b3cc6e8a03bb4d88600f8dbda2add8e6407705c159b0c63151036e77a1af |
| macOS amd64 | 91c5fbd493274b545b03ef32a89c2a21238393c0c0b1108210967199b3230d9d |
| macOS arm64 | 08bfef98b50c553df122bb34ee8dcf415cae7d3b108891488964a0df07aa2aeb |

All four were matched against upstream release digests/checksums and independently
verified using Python Sigstore 4.5.0 with a clean HOME and its own TUF bootstrap.
The authenticated upstream signer is
https://github.com/cli/cli/.github/workflows/deployment.yml@refs/heads/bagtoad/go-1-27-3-patch-on-v2-102-0,
issuer https://token.actions.githubusercontent.com, source commit
89d7dcec017194af1d6f8853176b2dae9c1da762. The release's patch branch is recorded
explicitly, not assumed to be trunk. Public upstream bundle/checksums and
bootstrap metadata are retained in [vendor/attestation](../../vendor/attestation/README.md).
Python Sigstore is a capture/review tool, not a new Atlas runtime dependency.

The root snapshot originated through the verified CLI's built-in TUF bootstrap
using gh attestation trusted-root in a fresh isolated HOME. The selected Public
Good output line is packaged as trusted-root.jsonl:
SHA-256 **3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1**,
identity **sigstore-public-good-2026-10-21**. It is CLI-reserialized public trust
material, so its bytes differ from the original TUF target; retained TUF metadata
documents that distinction. It is independent of the connector catalogue.

This bootstrap still relies on the independently maintained verifier/toolchain,
Sigstore bootstrap keys and reviewed Atlas source/release acquisition. Atlas
release archives themselves retain the existing checksum-only distribution
claim; B1.2 does not add signing to Atlas releases.

## Build, install and upgrade

Docker's API Dockerfile runs python -m scripts.prepare_attestation_verifier at
build time, before USER atlas. The fixed path is
/app/app/attestation/bin/gh. Its lock/roots are adjacent. Root owns the tree;
binary mode is 0555, roots 0444. Bootstrap staging uses the API image.
Worker and execution-runtime Dockerfiles do not install the binary.

The native fresh-install and upgrade build_application path prepares the same
distribution as root under
/opt/atlas/apps/api/app/attestation/bin/gh. Existing ProtectSystem=strict,
NoNewPrivileges and unprivileged service accounts remain intact. There is no new
privilege, queue, worker role or runtime dependency. A native worker shares the
installation tree but does not call the provenance verifier.

The preparation module is standard-library code: fixed upstream HTTPS download
at build/install time, archive SHA-256 check, extraction of only the expected
binary member, extracted-binary SHA-256 check, atomic installation, readonly
permissions. Runtime rechecks binary/root integrity and exact CLI version on each
call. There is no startup download or host-gh fallback.

For offline builds/upgrades, place the exact reviewed target-platform archive
under apps/api/app/attestation/archives/ in the extracted release package.
The native helper copies it; Docker includes it as a verified build input.
A corrupt present archive fails without a network fallback. Acquire other
existing Atlas build dependencies separately; this does not make the whole
Atlas installer an air-gapped dependency manager.

Development/CI preparation from apps/api:

~~~bash
python -m scripts.prepare_attestation_verifier
# Or, after independently obtaining the locked platform archive:
python -m scripts.prepare_attestation_verifier --archive /absolute/path/to/archive
python -m pytest tests/test_official_provenance.py tests/test_attestation_distribution.py -q
~~~

The resulting bin directory is ignored by Git and excluded from Docker contexts.
Ordinary tests use frozen evidence and never access GitHub. CI provisions the
locked binary before tests, and missing/corrupt dependencies fail tests rather
than skip genuine verification. Local macOS arm64 and Docker API Linux
arm64/amd64 builds and offline verification were exercised. amd64 was emulated
on an arm64 Docker host. macOS amd64 binary provenance was verified; execution
on an Intel Mac was not tested. Offline native-path preparation under /opt/atlas and subsequent unprivileged
verification were also smoke-tested in disposable Linux amd64/arm64 containers.
Full native Debian/systemd installation, reboot and upgrade remain operator
acceptance requirements.

## Rotation and offline limitations

1. Review upstream release/security changes and actual flags/output before
   changing the pinned version. Independently authenticate each supported archive;
   check archive and extracted-binary digests. Preserve upstream provenance.
2. Refresh roots only in an isolated maintenance environment using authenticated
   TUF with independently trusted bootstrap roots. Review changes in CA/log keys,
   validity windows and incident/revocation guidance. Keep the original signed
   metadata and capture identity.
3. Change the root ID/hash, distribution lock, exact-version check and policy
   version when semantics change. Run genuine old/current fixtures and all
   adversarial tests on supported architectures. Review notices.
4. Distribute through a trusted Atlas release/image upgrade. Offline operators
   transfer the reviewed release and locked binary archives through their trusted
   process. The native upgrade replaces application roots/code together; no
   database migration is required. Never overwrite roots from catalogue metadata.

A frozen root can validate an old signature while lacking knowledge of a later
revocation or compromised key. TUF snapshot freshness is checked during capture,
not during offline verification. The frozen timestamp metadata is historical
evidence, not an evergreen online update source. Long-lived installations require
operator security updates; successful offline verification is not a claim of
current revocation awareness. Unhandled process/host termination can leave a
0700 temporary workspace for normal OS temporary-file cleanup.

## Publication boundary and prerequisites for B1.3/B3

B1.3 now calls this unchanged verifier from its [bounded official consumer](official-catalogue.md).
Live retrieval and cryptographic verification were exercised on 21 October 2026;
promotion failed closed with `publication_not_immutable`. Durable trust foundations
and global manual-refresh/status APIs are present, but no live remote catalogue
is accepted. The [separate publication plan](../architecture/integrations/b1-3-publication-plan.md)
is required before that gate can be implemented for an advancing current channel.

On 21 October 2026, GitHub's release API reported catalogue-v1
(release 416561696) and proxmox-v0.2.0 (416290807) as immutable: false.
The checked-in connector workflows attest builds in connector-release and upload
candidate artifacts; neither publishes releases. Their environment reference
does not prove environment reviewer rules, tag protection or later human approval.

| Guarantee | Evidence / remaining gate |
| --- | --- |
| Artifact bytes and signer/source identity | Cryptographically enforced by B1.2 |
| Numeric repository/owner identity | Independently checked API identity plus authenticated certificate extensions |
| Subject filename | Signed workflow assertion checked against expected name |
| Release ID / release-asset ID | API/catalogue metadata; absent from these build attestations |
| Release approval | Not established by build provenance; publication-side control needed |
| Immutable historical releases/snapshots | Not provided by the two existing mutable releases |
| Current-catalogue pointer/freshness | Not part of provenance; B1.3 retrieval/acceptance and later freshness policy |
| Installation/execution authority | Existing gates remain; B3 must add authenticated package eligibility |

Before B1.3/B3 production remote acceptance, the operator must establish and audit
immutable versioned package releases and immutable historical catalogue snapshots.
Use a separate mutable discovery pointer to the newest immutable snapshot;
catalogue-v1 cannot simultaneously be an immutable release and a mutable asset
container. Preserve sequence-1 bytes/evidence without silently replacing them.

Publication recommendation (not applied): require protected main reviews and
protected release tags; protect connector-release with explicit reviewers;
restrict catalogue preparation to main; keep signing workflows pinned/reviewed.
Publish an approved candidate into a draft versioned release, verify each exact
asset against its build attestation, then publish with GitHub release immutability
enabled. Verify immutable=true and the resulting release/asset identities before
updating a separate current pointer. Record approval separately from the build
claim. Generalize the connector release workflow's current Proxmox-only trigger
and tag validation deliberately when future connectors are published. Atlas's
verifier already uses generic IDs; it needs no vendor exception.

No repository settings, workflow publication behavior, releases or tags were
changed. Existing source attestation identities remain compatible.

## Frozen acceptance and handoff

The [fixture record](../../apps/api/tests/fixtures/official_catalogue/README.md)
documents genuine sequence 1 and package evidence. To test an independently
obtained Proxmox 0.2.0 package without installing or executing it:

~~~bash
PYTHONPATH=apps/api python infra/ci/verify-official-fixtures.py --package /absolute/path/proxmox-0.2.0.tar.gz
~~~

This opt-in script has no network access and requires the expected frozen digest.
Package bytes are not committed. The normal suite requires the real CLI for the
catalogue positive case and cryptographic tampering failures. Policy-unit tests
alter actual verified output only to test rejection, never to fabricate success.

B1.3 must retain original bytes, structurally validate them, call verify_catalogue,
bind evidence to those same bytes and subject, then apply durable monotonic
sequence acceptance transactionally. Equal sequence with changed content,
rollback, absence versus withdrawal, refresh time and publication authority
need explicit treatment. Do not treat a mutable returned document dictionary as
authenticated state. B3 must separately call verify_package for executable bytes.
Neither evidence type grants tenant access or bypasses administrator approval.
