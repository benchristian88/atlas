# Release packages and verification

Obtain packages from the [official Atlas Impact releases](https://github.com/benchristian88/atlas/releases).
Choose Docker Compose or native/systemd and keep API/frontend components from
that same package together. If no release asset is published yet, use the separate
development workflow or wait for the packaged beta.

## Version and source

`apps/api/app/release.json` is the application version/channel authority. The
checked-in version is `0.1.0` in the `beta` channel. Packages also carry their
commit/build identity and installation method. View installed identity in
System Settings → About. Tooling package versions are not a separate Atlas release.

Stable installations consider stable releases; beta installations consider beta
and stable versions using semantic version ordering. Build identifiers do not
change version ordering. [Update checking](upgrades.md#update-awareness-and-offline-operation)
is informational and does not install anything.

## Assets and validation

A release contains:

- `atlas-docker-compose-<version>.tar.gz`;
- `atlas-systemd-<version>.tar.gz`;
- `atlas-release-<version>.json`;
- `SHA256SUMS`, covering both archives and the release manifest.

Download **your chosen archive, the release manifest and `SHA256SUMS` from the
same official HTTPS release** into a new working directory. Docker Compose users
need only the Docker archive; native/systemd users need only the systemd archive.
The unrelated archive is not required.

Set the exact downloaded version and package type:

```bash
ATLAS_VERSION=0.1.0
ATLAS_PACKAGE=docker-compose
```

Use `ATLAS_PACKAGE=systemd` for native/systemd. Select the two checksum entries by
their exact filenames. The command fails if either entry is missing or duplicated:

```bash
awk -v package="atlas-${ATLAS_PACKAGE}-${ATLAS_VERSION}.tar.gz" \
    -v manifest="atlas-release-${ATLAS_VERSION}.json" '
  $2 == package { package_count++; print; next }
  $2 == manifest { manifest_count++; print }
  END { if (package_count != 1 || manifest_count != 1) exit 1 }
' SHA256SUMS > SHA256SUMS.selected
```

Stop if selection fails. Before extracting, verify **both selected entries**.
On Linux:

```bash
sha256sum -c SHA256SUMS.selected
```

On macOS:

```bash
shasum -a 256 -c SHA256SUMS.selected
```

Both the chosen archive and manifest must report `OK`; stop if either file is
missing or differs. Do not use an option that ignores missing files.
SHA-256 detects corruption relative to the
checksum file; it is not a digital signature. Signing/attestations are not
currently part of the release contract.

After successful verification, extract the chosen package. For Docker Compose:

```bash
tar -xzf "atlas-docker-compose-${ATLAS_VERSION}.tar.gz"
cd "atlas-docker-compose-${ATLAS_VERSION}"
python3 infra/install/compose.py
```

For native/systemd, after preparing the [host prerequisites](installation.md#nativesystemd):

```bash
tar -xzf "atlas-systemd-${ATLAS_VERSION}.tar.gz"
cd "atlas-systemd-${ATLAS_VERSION}"
sudo python3 infra/install/native.py
```

Replace the example version with the downloaded release. Run these fresh-install
commands only for a new deployment. Use [upgrades](upgrades.md) for an existing one.
The package root name matches the archive name without `.tar.gz`.

## Package identity and contents

Each package includes `PACKAGE.json`, canonical version/channel/build/method
metadata, runtime/build inputs, installers, operator documentation and licence
notices. No runtime Git is needed. The release manifest records the selected
repository, tag/commit, schema compatibility, package sizes and hashes. Minimum
supported database revision is `20261004_0025`; pending migrations still run at
startup. Do not edit package identity to bypass validation.

Maintainers still verify the complete release with both archives using the
[release verifier](../development/releasing.md#local-dry-run); selecting operator
checksums does not change its package/manifest identity or contents checks.
The packager and verifier reject unsafe archive paths/links, duplicates, invalid
modes, missing required files, inconsistent identity and credential-like contents.
Caches, development tests, history, environment files, databases and backup
archives are excluded. Included documentation links locally where possible;
references to omitted source documents resolve to the official repository at
the package's recorded commit.

Maintainers use the separate [release development guide](../development/releasing.md)
and [distribution architecture](../architecture/release-distribution.md).
