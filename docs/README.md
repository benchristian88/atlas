# Atlas Impact documentation

Atlas is a self-hosted beta for infrastructure and operational knowledge.
Start with a release package, then build your inventory and connect it to the
Services you operate. See [project status](product/status.md) for the path to 1.0.

## Getting started

- [Installation and first run](deployment/installation.md) — supported Docker
  Compose and native/systemd packages, prerequisites and administrator setup.
- [Release packages and verification](deployment/releases.md) — obtain and
  verify the matching artifacts before extraction.
- [Encrypted backup and restore](deployment/backup-restore.md) — portable
  application backups, fresh restore and local disaster recovery.
- [Upgrades](deployment/upgrades.md) — use the new verified package while
  retaining configuration and data.

## Operations

- [Security policy and reporting](../SECURITY.md).
- [Local MFA and recovery](deployment/mfa.md).
- [Single-origin routing](deployment/single-origin.md) and
  [optional reverse proxies](deployment/reverse-proxy-examples.md).
- [Update checking and offline operation](deployment/upgrades.md#update-awareness-and-offline-operation).
- [Administration](admin/administration.md) — accounts, permissions, context,
  System Settings and audit.
- [Support and diagnostics](../SUPPORT.md).

## Knowledge and administration guides

- [Services, Service Types and Criticality](admin/service-types-and-criticality.md).
- [Knowledge profiles and requirements](admin/knowledge-profiles.md).
- [Knowledge Graph](admin/knowledge-graph.md).
- [Infrastructure Topology](admin/infrastructure-topology.md) and [Showcase](admin/showcase.md).
- [Asset Types](admin/asset-types.md), [Asset Categories](admin/asset-categories.md)
  and [Asset icons](admin/asset-icons.md).
- [Networks](admin/networks.md), [Relationship Types](admin/relationship-types.md)
  and [Topology Positions](admin/topology-positions.md).
- [Feature reference](product/feature-ledger.md) — implemented capabilities and
  explicit limits, backed by repository paths.

## Architecture

- [Product architecture](architecture/architecture-v0.md) and [data model](architecture/data-model-v0.md).
- [Authentication and access control](architecture/authentication-and-access-control.md)
  and [MFA](architecture/local-two-factor-authentication.md).
- [Services](architecture/service-model.md), [dependencies](architecture/service-dependencies.md),
  [operational graph](architecture/operational-graph.md) and
  [dependency impact analysis](architecture/dependency-analysis.md).
- [Knowledge and reconciliation](architecture/knowledge-changes-and-reconciliation.md)
  and [knowledge completeness](architecture/knowledge-completeness.md).
- [Deployment](architecture/deployment-and-upgrades.md),
  [encrypted backup](architecture/encrypted-backup-restore.md) and
  [release distribution](architecture/release-distribution.md).
- [UI architecture](architecture/ui-architecture.md),
  [topology](architecture/infrastructure-topology.md) and
  [entity lifecycle](architecture/entity-lifecycle.md).
- [Architecture decisions](decisions/README.md) — decision rationale; implementation
  is established by the current code and tests.

## Development

- [Contributing](../CONTRIBUTING.md) and [running from source](development/from-source.md).
- [Building and qualifying a release](development/releasing.md).
- [Development CI and local validation](testing/continuous-integration.md).
- [Authentication test plan](testing/auth-shell-test-plan.md) and
  [security/access test plan](testing/security-and-access-test-plan.md).
- [Licence](../LICENSE), [commercial licensing](../COMMERCIAL-LICENSING.md) and
  [third-party notices](../THIRD-PARTY-NOTICES.md).

Dated plans, implementation prompts and validation reports are preserved under
`docs/history/`. They describe past work and are outside the normal operator
documentation journey. Test plans and historical results do not establish that
a current build has passed validation.
