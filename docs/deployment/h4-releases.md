# Atlas release operator guide

H1/H1.1, H2 and H3 are ACCEPTED. H4 implements package distribution and
informational update awareness; publication and actual native lifecycle remain
separate acceptance gates. See [release architecture](../architecture/release-distribution.md)
and [H4 validation](../testing/h4-release-distribution.md).

## Version and source

`apps/api/app/release.json` is the sole application version/channel authority.
The current policy retains `0.1.0` / `beta`. Use SemVer; stable versions have no
prerelease identifier. Beta versions may be numeric or `X.Y.Z-beta.N`. Build
metadata has no ordering effect. Beta maps to GitHub prerelease, stable to a
normal release. At equal SemVer, stable supersedes beta. Each release needs a
new version and tag; never reuse a numeric beta tag for stable promotion.
`package.json` remains tooling metadata. CI never bumps versions or creates tags.

Official source: [benchristian88/atlas releases](https://github.com/benchristian88/atlas/releases).
Repository identity is centralized in `apps/api/app/release.py`.

## Local dry run

From a clean committed release checkout:

```bash
python3 infra/release/release.py metadata --tag v0.1.0
python3 infra/release/release.py build --dry-run --tag v0.1.0 --output /tmp/atlas-release-check
python3 infra/release/release.py verify --tag v0.1.0 --output /tmp/atlas-release-check
cd /tmp/atlas-release-check
sha256sum -c SHA256SUMS
```

Use the actual metadata version instead of the example. Output must be an empty
or new directory. For implementation acceptance before committing, add
`--worktree` to `build --dry-run`. This includes reviewed paths from tracked and
unignored pending source files, records `source_state: working_tree` and a
source digest, and is rejected by publication verification. It does not pretend
that the working tree is the recorded base commit. No command above can publish.

## Assets and validation

Each release has:

- `atlas-docker-compose-<version>.tar.gz`, root with the same name minus `.tar.gz`;
- `atlas-systemd-<version>.tar.gz`, similarly named root;
- `atlas-release-<version>.json`;
- `SHA256SUMS`, covering both packages and the manifest.

The reviewed `infra/release/package-manifest.json` selects runtime trees, build
inputs, installers, gateway/units and operator documentation. Native packages
require `infra/nginx/native.conf` and `infra/install/native_ingress.py`; both
construction and verification reject missing native ingress inputs. Package creation
uses a committed Git snapshot; caches, `.env`, data, Git state, development tests
and backups are excluded. Each package carries `PACKAGE.json` and injected
canonical metadata with commit SHA and install method. No runtime Git is needed.

The manifest records product/repository, schema version, Atlas version/channel,
tag, commit, commit-time UTC timestamp, source state/digest, supported methods,
minimum/current database revisions, and package hashes/sizes. Minimum schema is
H1 `20261004_0025`; current head is determined from the migration graph. It is an
upgrade/recovery compatibility declaration, not permission to skip migrations.
No credentials or installation settings appear in the manifest.

Validation reads archive members without trusting extraction paths, rejects
links, traversal, duplicate files, unsafe modes, unknown contents and sensitive
file types, verifies required runtime files, Docker COPY inputs and frontend
relative imports, and compares package/release identities, schema and checksums.
Included documentation remains locally linked; links to omitted source documents
point to the official repository at the exact commit, avoiding development-file
bloat in production packages.
Tests extract validated packages in temporary directories and invoke installer
help/upgrade validation paths. Always verify before extracting a downloaded file.

`SHA256SUMS` is a corruption check, **not a digital signature**. Download it and
the desired package from the official HTTPS release. On Linux run
`sha256sum -c SHA256SUMS` with all listed assets present; on macOS use
`shasum -a 256 -c SHA256SUMS`. H4 does not implement signing or attestations.
Official GitHub attestations were inspected; their OIDC/attestation permissions
and publication/verification lifecycle are deferred until the repository release
policy is exercised. No home-grown scheme or paid dependency is introduced.
See [GitHub attestation guidance](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations).

Sorted USTAR entries, normalized owners/modes, commit timestamps and a zero-time
unnamed gzip header make package and manifest bytes deterministic for the same
selected source, version and commit with the same Python/zlib toolchain. A
working-tree dry run also records its actual selected-source digest. This proves
package reproducibility; native dependency builds and Docker images remain
outside the byte-for-byte claim because upstream image tags/wheels/toolchains
are external inputs.

## Deliberate publication

1. Change canonical metadata intentionally, review release/migration notes and
   merge the version commit into `dev` through the usual review process.
2. Run the full product release gates, dependency audit and local dry run.
3. An authorized operator creates and pushes exactly `v<version>` at the reviewed
   commit. This is the explicit release action; ordinary pushes cannot publish.
4. The release workflow checks the tag against metadata and requires its commit
   to be reachable from `dev`. It tests and packages that exact commit, builds the
   production frontend, validates both artifacts and verifies checksums.
5. Only the final job receives `contents: write`. It downloads validated assets,
   rechecks identity/checksums and uses native `gh release create --verify-tag`
   with generated notes and the metadata-derived prerelease flag. It does not
   create a tag, alter versions or publish images. Existing releases are refused.

The workflow uses immutable official Action SHA pins, read-only/default-empty
permissions, no persisted checkout credentials and no PR publication trigger.
`workflow_dispatch` runs the same pipeline **only as a dry run**, on the chosen
checkout. It uploads validated assets for review but cannot publish. Publication
checks exclude working-tree manifests. Tag protection and reviewed `dev` changes
remain repository operator responsibilities. Do not dispatch a real release for
H4 acceptance. GitHub-hosted execution must be reported separately from local
workflow syntax/policy checks.

GitHub references: [release API](https://docs.github.com/en/rest/releases/releases),
[workflow permission syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
and [native release CLI](https://cli.github.com/manual/gh_release_create).
