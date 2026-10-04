# Release distribution and update awareness

The canonical version and channel remain in `apps/api/app/release.json`.
Release packages use the existing Docker local-build and native/systemd installers.
Release packages carry reviewed runtime source/build material, an immutable
commit identity and method identity; production operators acquire a package
instead of cloning an arbitrary branch. No container registry is introduced.

Local-build distribution avoids adding registry credentials, image publishing
and a second deployment contract during beta. Package bytes are reproducible
from the same source, commit and commit timestamp; dependency installation and
container builds are not claimed byte-reproducible. Existing upstream image
tags and Python wheels remain external inputs. Registry digests, signing and
GitHub attestations are deferred to later hardening; SHA-256 detects corruption
and is not a digital signature or independent proof of publisher authenticity.

The current `0.1.0` / `beta` split is retained. Versions follow SemVer 2.0.0;
tags are exactly `v<version>`. Stable metadata forbids a SemVer prerelease.
Beta permits numeric versions or `-beta.<number>` prereleases. Build metadata
does not affect precedence. At equal semantic version, stable supersedes beta.
Changing a beta numeric release to stable requires a new version/tag because
one tag cannot identify two releases. Beta maps to GitHub `prerelease: true`;
stable maps to false. The developer changes metadata deliberately before tagging.

System Settings owns informational update awareness. The global
`system_settings.manage` boundary protects the normalized API; About retains
installed identity. The server reads only the fixed official repository's
public release list, without tokens, tenant data, redirects or ambient proxy
credentials. Stable selects stable releases only. Beta selects supported beta
or stable releases by semantic precedence, then channel precedence. Drafts,
unsupported prereleases and malformed records are excluded. No release body
or remote commands reach the browser. No package download or host control exists.

The cache is process-local and non-authoritative: successful results last four
hours, unavailable results five minutes, deliberate refreshes at least sixty
seconds apart per process. Concurrent requests share one bounded fetch. Network
requests have a five-second total timeout, at most 1 MiB across at most three
100-record pages. Pagination is generated locally, never followed from remote
links. Incomplete listings fail safely. Startup makes no GitHub request, and
network/metadata failures return `unavailable` without affecting Atlas operations.

See [operator release guide](../deployment/releases.md) for manifests,
checksums and installation, the [maintainer guide](../development/releasing.md)
for dry runs and publication, and
[upgrade guide](../deployment/upgrades.md) for configuration-preserving
operator procedures and encrypted recovery. No persistence or migration changes are
required, and existing knowledge/graph/authentication contracts remain intact.

The native package includes a required nginx template and standard-library
ingress helper to the reviewed native package. They implement the existing
single-origin contract with loopback-only API/web, explicit proxy trust and 2 GiB restore
upload bounds. Installer preflight precedes durable Atlas mutation; nginx alone
is installed through distribution apt packages. Native upgrade/validate-only
reuse these checks, preserve protected configuration and update only managed
nginx paths with validation/rollback. Original lifecycle findings are recorded
in historical validation; later supplied
Debian 13 restore/packaged-upgrade confirmation is appended separately.
