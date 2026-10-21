# Reviewed attestation verifier bootstrap evidence

These are public verification materials, not executable binaries or credentials.
Captured 21 October 2026 from GitHub cli/cli release v2.102.1 and authenticated
Sigstore TUF. The runtime consumes only the release-owned
[distribution lock](../../apps/api/app/attestation/distribution.json) and
[trusted root](../../apps/api/app/attestation/trusted-root.jsonl).

- gh-2.102.1-checksums.txt is the upstream release checksum asset, SHA-256
  7b35c23de1547377b2c3276e2e4f02b3c44a4ce2686e3fe00a77a9c48b0daa8d.
- gh-2.102.1.sigstore.json is the genuine workflow bundle covering all four
  supported archive digests (and other upstream release subjects), SHA-256
  0fce1f9e3925aed803073481f6bf5aea98617358424719926e9fd86cdc08044b.
  GitHub's public digest-attestation API also returned a separate GitHub release
  attestation; this retained bundle is the deployment workflow build attestation.
- tuf-bootstrap/ contains the Public Good root, targets, snapshot and timestamp
  metadata plus original trusted_root.json target from the clean gh trusted-root
  capture. Original target SHA-256:
  6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66.
  CLI output uses its own canonical representation; the packaged root SHA-256 is
  3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1.
  Root metadata version 16, targets 14, snapshot 166, timestamp 813.
  The timestamp expires 2026-10-27T07:33:11Z; these are historical capture records,
  not a current TUF mirror or instructions to ignore expiry.

Each Linux amd64/arm64 and macOS amd64/arm64 archive passed a separate
Python Sigstore 4.5.0 verification with its independent bootstrap, fresh HOME,
no GitHub login and these exact expectations:

~~~bash
python -m sigstore verify identity \
  --bundle vendor/attestation/gh-2.102.1.sigstore.json \
  --cert-identity 'https://github.com/cli/cli/.github/workflows/deployment.yml@refs/heads/bagtoad/go-1-27-3-patch-on-v2-102-0' \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  /absolute/path/to/gh_2.102.1_linux_amd64.tar.gz
~~~

The upstream release commit is 89d7dcec017194af1d6f8853176b2dae9c1da762.
The upstream certificate and signed source dependency agree on that commit.
No claim is made that downloading a checksum from the same server independently
authenticates a binary. Pinned digests were corroborated by genuine attestation
verification. Maintainers must review these pins through the normal trusted
Atlas source/release process.

See [deployment and rotation](../../docs/deployment/attestation-verification.md)
for offline limits, exact platform hashes, tests and upgrade requirements.
