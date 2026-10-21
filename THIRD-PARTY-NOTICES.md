# Third-party software

Atlas Impact is licensed AGPL-3.0-only. Dependencies, base images, fonts and
other third-party software retain their respective licences; Atlas's licence
does not replace them.

The pinned JavaScript dependency inventory is in
[package-lock.json](apps/web/package-lock.json). Python dependencies are declared
in [API requirements](apps/api/requirements.txt) and plugin package metadata.
Deployment also uses PostgreSQL, Redis, nginx and Python/Node base images.
Inter Variable comes from the pinned font package and uses the SIL Open Font
License. Refer to the installed components' licence notices and upstream sources
when redistributing them; this document is not an exhaustive dependency licence
audit.

The separately deployed Atlas Ansible Runtime pins its complete Python baseline
in [requirements.lock](apps/runtime/ansible/requirements.lock). Its initial
[CycloneDX inventory](apps/runtime/ansible/sbom.cdx.json) records exact versions,
reference wheel hashes and licence metadata; [upstream notices](apps/runtime/ansible/notices)
are retained verbatim. The inventory covers reference Python wheels, not a final
image/OS or every native platform licence audit. Ansible and its GPL dependencies
remain in the isolated runtime environment; Atlas API does not import Ansible.

I4A distributes the exact community.proxmox 2.0.0 source archive under
[vendor/collections](vendor/collections), pinned by the
[collection lock](apps/runtime/ansible/collections.lock.json). Its original
GPL-3.0-or-later and BSD-2-Clause licence material is retained in the archive
and runtime notices. Added HTTPS dependencies are proxmoxer 2.3.0 (MIT),
requests 2.34.2 (Apache-2.0), charset-normalizer 3.5.2 (MIT), idna 3.20
(BSD-3-Clause), urllib3 2.8.0 (MIT) and certifi 2026.7.22 (MPL-2.0).
Exact artefact hashes and original notices are in the runtime SBOM/notices.
No third-party implementation is relicensed as Atlas-authored Connector code.

External Asset icon sources are operator-selected. Confirm permission to use
their artwork; Atlas does not grant rights to third-party logos.

The separate `atlas-connector-sdk` and official `atlas-connectors` projects use
Apache-2.0 under the accepted ownership boundary. Atlas and its runtime source
remain AGPL-3.0-only. The exact SDK 1.1.0 wheel and hash lock are in
[vendor/sdk](vendor/sdk); SDK upstream notices are also included in
[runtime notices](apps/runtime/ansible/notices/atlas-connector-sdk). The bundled
Proxmox archive includes its Apache licence, NOTICE and SPDX inventory. No legacy
AGPL implementation was copied into these Apache projects. These engineering
ownership records do not replace upstream redistribution/licence review.

B1.2 packages GitHub CLI 2.102.1 at the API/installation boundary, separately
from the execution runtime. Its upstream [MIT licence](apps/api/app/attestation/LICENSE.gh),
[pinned distribution](apps/api/app/attestation/distribution.json) and
[public verification evidence](vendor/attestation/README.md) accompany Atlas.
Upstream Go dependencies retain their own licences; this is not an exhaustive
transitive licence audit. Sigstore public trust metadata is used only for
verification and is not secret key material. No Python Sigstore runtime
dependency is added.
