# Project status

Atlas Impact is a beta product progressing toward 1.0.0, with a homelab and
self-hosted focus. No date is promised for 1.0.0.

## Current

- Core Atlas platform: scoped inventory, Services, Business Functions,
  administration and operational views.
- Secure deployment: packaged Docker Compose and native/systemd installation,
  protected first-run setup, local authentication and optional MFA.
- Encrypted backup and restore, portable across supported deployment methods.
- Dependency impact analysis, accepted knowledge, provenance, reconciliation
  and knowledge completeness.
- Release packages, checksum verification, configuration-preserving upgrades
  and informational update checking.
- Development CI and operator documentation for installation, recovery and updates.
- Isolated authenticated local integration runtime and offline Connector catalogue,
  with global verified-package state and Configured/Catalogue/Runtime views.
  Generic scoped configuration, write-only encrypted credentials, global taxonomy
  mappings and bounded Test Connection are implemented. Proxmox is probe-only and
  unqualified. Live Docker upgrade and fingerprint-pinned Proxmox 9.2.11 connection
  acceptance are operator-confirmed, including saved probes after runtime restart.
  Docker/Compose and UniFi source Connectors remain metadata only. I3 implements generic
  asynchronous discovery orchestration, fixed schedules, canonical AIP ingestion and
  run history with deterministic test-only execution; no production discovery
  Connector is shipped. Actual I3 Docker/LXC build/deployment, migration, saved I2
  probes, signing-state restart preservation and isolation/hardening are
  operator-confirmed. Native Debian/systemd I3 LIVE acceptance remains outstanding.

Core platform hardening is substantially complete and sufficient to proceed to
integration/plugin and onboarding development. This includes secure installation,
authentication/MFA, encrypted backup and restore, release packaging, upgrades,
update awareness, CI and operator guidance. It is not final production security
certification or 1.0.0 release qualification.

See the [feature reference](feature-ledger.md) for implemented scope and limits.
Dependency impact analysis uses recorded knowledge and hypothetical scenarios;
it is not live monitoring or evidence of recovery readiness.

## Next development

- Catalogue-driven integrations follow the accepted
  [Integration architecture](../architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md)
  and [phased roadmap](../architecture/integrations/integration-roadmap.md):
  architecture/contracts, runtime/catalogue and generic configuration/secrets are
  implemented through I3. Next are Proxmox, Docker/Compose, local
  UniFi infrastructure, onboarding and final integration acceptance. The current
  Proxmox Connector remains probe-only; vendor discovery is not implemented. Core hardening is retained, with its acceptance gaps.
  The [I2 validation record](../architecture/integrations/i2-completion-report.md)
  records completed SDK extraction, live Docker/Proxmox connection acceptance and
  the remaining native/systemd, remote provenance and I4 qualification boundaries.
  The [I3 record](../architecture/integrations/i3-completion-report.md) documents generic
  orchestration, test-only execution and subsequent actual Docker/LXC operator
  acceptance. Native live acceptance, remote GitHub/Sigstore qualification and I4
  Proxmox discovery/9.2.11 qualification remain outstanding.
- Guided onboarding to help operators establish useful initial knowledge.

## Before 1.0

- Complete the integration/plugin and guided onboarding workflows above.
- Final UX refinements, feature documentation, current screenshots and documentation freeze.
- Final dependency/security review, including reassessment and remediation or
  explicit disposition of known dependency findings.
- Whole-product security/release qualification after integrations and onboarding,
  including integration credentials, remote API access, execution and trust boundaries.
- Final supported-platform and cross-deployment acceptance. Real packaged Docker
  upgrade acceptance remains outstanding; fresh remediated native installation,
  native restart/reboot and deployed MFA recovery commands also need explicit
  lifecycle evidence.

The documentation structure is intended to remain stable as these features land:
extend their guides, update installation/onboarding where needed, refresh visuals,
then complete the final documentation freeze and release review.
