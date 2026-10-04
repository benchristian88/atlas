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

See the [feature reference](feature-ledger.md) for implemented scope and limits.
Dependency impact analysis uses recorded knowledge and hypothetical scenarios;
it is not live monitoring or evidence of recovery readiness.

## Before 1.0

- First-party integrations/plugins with a usable configure, test, run and review
  workflow. The Proxmox adapter and plugin contracts are existing foundations.
- Guided onboarding to help operators establish useful initial knowledge.
- Final UX refinements, feature documentation and current screenshots.
- Final security review and release qualification.

The documentation structure is intended to remain stable as these features land:
extend their guides, update installation/onboarding where needed, refresh visuals,
then complete the final documentation freeze and release review.
