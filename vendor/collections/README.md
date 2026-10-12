# Reviewed runtime Collections

Atlas-owned offline artefacts, using the same repository vendor/release boundary
as `vendor/sdk`. The canonical identity and compatibility record is
`apps/runtime/ansible/collections.lock.json`; both runtime installers and release
verification check it. Do not install from a floating Galaxy name or replace an
archive without a dated source/dependency/licence review and new lock identity.

community.proxmox 2.0.0 was reviewed on 12 October 2026. Its unmodified Galaxy
archive includes upstream source, copyright headers and GPL-3.0-or-later /
BSD-2-Clause material. Copies of notices are distributed with the isolated
runtime, whose SBOM records the archive SHA-256. This groundwork does not enable
Proxmox discovery or qualify any source version.
