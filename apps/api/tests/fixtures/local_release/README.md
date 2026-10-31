# Genuine Proxmox 0.2.2 release evidence

Captured by public HTTPS GET on 31 October 2026 from
`benchristian88/atlas-connectors`, immutable release `429608780`, tag
`proxmox-v0.2.2`, source commit `e58788a667c0c0006477ac149e8ad28aedda0745`.
The original archive, detached manifest and original Sigstore bundle are unchanged.

| Asset | ID | SHA-256 |
| --- | --- | --- |
| proxmox-0.2.2.tar.gz | 693849044 | 2d66fc69b9cf9c70d7df117fe41bff3e3e056299f1908cde965e9e3f75e59abf |
| manifest.json | 693848071 | dca85fd12d377f1fc8c20adda39334a628eacb427ab6ca84511e14c80f382109 |
| package.sigstore.json | 693848554 | 126acccfe5b446162a64052f88a9b91e216f9d80fc3dfbb362f30f051b5ec50f |

`release.json` and `tag-ref.json` retain public provider responses. These are
frozen observations, not signature or publication authority. Normal tests use
synthetic transport around those responses and exercise real offline cryptography;
they do not claim fresh GitHub observations. The implementation task separately
ran the existing `GithubAttestationVerifier.verify_package()` against fresh public
downloads, then ran the new live verification-only CLI successfully.

The authenticated signer is the existing fixed `release.yml@refs/tags/proxmox-v0.2.2`
identity; issuer is GitHub Actions OIDC, numeric repository/owner are
1414494920/93822871, original build run is 41147363156 attempt 1. Rekor witnessed
the signature at 2026-10-30T23:58:36Z. Verification used GitHub CLI 2.102.1 and
the unchanged `sigstore-public-good-2026-10-21` root snapshot (SHA-256
3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1).

Tests never execute this package against a source. Root/PostgreSQL lifecycle tests
stage its original bytes and verify the independent runtime store checks. Source
execution and LXC operational acceptance remain separate human gates. Package
licence/notices remain inside the unchanged archive; these fixtures confer no
catalogue or deployment authority.
