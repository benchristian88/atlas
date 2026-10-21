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
They do not verify the catalogue attestation, authenticate a publisher, or
make any entry eligible for installation. B1.2 owns cryptographic verification.
