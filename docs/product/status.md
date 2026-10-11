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
  architecture/contracts alignment, then isolated runtime/catalogue, generic
  configuration/secrets, orchestration/ingestion, Proxmox, Docker/Compose, local
  UniFi infrastructure, onboarding and final integration acceptance. The current
  Proxmox adapter/plugin contracts remain foundations; target design is not live
  configured discovery. Core hardening is retained, with its acceptance gaps.
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
