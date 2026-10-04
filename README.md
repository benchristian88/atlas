# Atlas Impact

Atlas Impact is a self-hosted operational knowledge platform. Record your
infrastructure, connect it to the Services you rely on, and explore what a
dependency failure could mean using the knowledge you have accepted.

For a homelab or small IT environment, Atlas brings inventory, diagrams,
dependency explanations and missing documentation into one place. Manually
curated knowledge is first-class; you can start without a discovery integration.

[![CI](https://github.com/benchristian88/atlas/actions/workflows/ci.yml/badge.svg)](https://github.com/benchristian88/atlas/actions/workflows/ci.yml)

## What Atlas does

- **Inventory and context:** Assets, Interfaces, Networks, customers and sites,
  with managed types and custom fields.
- **Services and Business Functions:** describe operational capabilities and
  the infrastructure and other Services that support them.
- **Knowledge Graph and Infrastructure Topology:** explore recorded connections,
  hosting, network membership and technical connectivity.
- **Dependency impact analysis:** preview an unavailable Asset or Service and
  inspect bounded, explainable consequences from recorded dependency rules.
  Unknown effects stay unknown; a connected node alone is not proof of failure.
- **Knowledge completeness:** configurable requirements and gaps show where
  accepted knowledge is missing, stale or incomplete.
- **Provenance and review:** assertions, history, Changes, discovery simulation
  and reconciliation keep observations separate from accepted knowledge.
- **Local administration:** scoped permissions, secure first-run setup, local
  authentication, optional TOTP MFA and audit history.
- **Recovery and updates:** passphrase-encrypted portable backups, packaged
  installation and upgrades, and informational release checks.

Atlas helps answer what exists, what supports it and what your recorded
dependencies imply. It complements monitoring with curated operational context.
Analysis describes a hypothetical scenario; it does not measure live availability
or certify recovery readiness.

## Current status

Atlas is an actively developed **beta** focused on homelab and self-hosted use.
The core platform, secure deployment, backup/restore, dependency and knowledge
capabilities, and release/update infrastructure are implemented. First-party
integration workflows and guided onboarding are the substantial remaining
product work toward **1.0.0**, followed by final UX, documentation, screenshots
and security/release qualification. There is no promised release date.

The Proxmox adapter and vendor-neutral plugin contracts exist, but live
configure/test/run/reconcile operation is not yet an end-to-end product feature.
See the [project status](docs/product/status.md) and
[feature reference](docs/product/feature-ledger.md) for current boundaries.

## Installation

Use a verified package from the [official releases](https://github.com/benchristian88/atlas/releases).
If no release asset is published yet, wait for a packaged beta or use the
explicitly separate [development workflow](docs/development/from-source.md).

| Method | Start from the verified, extracted package | Guide |
| --- | --- | --- |
| Docker Compose | `python3 infra/install/compose.py` | [Docker installation](docs/deployment/installation.md#docker-compose) |
| Native/systemd | `sudo python3 infra/install/native.py` | [Host prerequisites and installation](docs/deployment/installation.md#nativesystemd) |

Both methods generate protected configuration and print one usable Atlas URL
and a one-time setup code. Open that URL to create the first administrator or
restore an encrypted backup. Atlas provides a single browser endpoint, including
`/api`; an optional HTTPS proxy forwards to that one endpoint.

Read [package verification](docs/deployment/releases.md#assets-and-validation)
before installation and [packaged upgrades](docs/deployment/upgrades.md) before
updating an existing deployment. Git is not required for production installation.

## Security and recovery

The API enforces permissions and customer/site scope. Production installers
generate independent database, session and data-encryption secrets. MFA is
optional per account; backups are encrypted with an operator-held passphrase.
Use HTTPS for access beyond a trusted local environment and keep host access
and deployment configuration protected.

See [security reporting and policy](SECURITY.md),
[MFA and local recovery](docs/deployment/mfa.md),
[encrypted backup/restore](docs/deployment/backup-restore.md) and
[reverse-proxy guidance](docs/deployment/reverse-proxy-examples.md).

## Documentation

Start at the [documentation index](docs/README.md) for installation, first run,
operations and administration. Deeper references cover the
[architecture](docs/architecture/architecture-v0.md),
[dependency model](docs/architecture/service-dependencies.md),
[authentication](docs/architecture/authentication-and-access-control.md),
[UI standards](docs/architecture/ui-architecture.md) and
[development checks](docs/testing/continuous-integration.md).

## Licence, contributions and support

Atlas Impact is licensed **AGPL-3.0-only**. See [LICENSE](LICENSE).
Alternative commercial licensing may be available separately; the repository
grants only the AGPL licence. See [commercial licensing](COMMERCIAL-LICENSING.md).
Third-party software retains its [respective licences](THIRD-PARTY-NOTICES.md).

Bug reports, feedback and feature discussion are welcome. Discuss external code
contributions with the maintainer before submission. See
[contribution guidance](CONTRIBUTING.md) and [support](SUPPORT.md).
