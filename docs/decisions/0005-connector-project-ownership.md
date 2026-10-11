# 0005 — Three-project Integration ownership and licences

Status: **Accepted**

Date: 2026-10-11

## Context

Atlas and current in-repo SDK/Proxmox metadata are AGPL-3.0-only. The protocol
needs one source shared by application and future official Connectors; no separate
SDK/Connector repository is created by this task.

## Decision

`atlas` remains AGPL-3.0-only application/platform and hosts runtime source in v1.
`atlas-connector-sdk` is a separate Atlas-owned Apache-2.0 protocol/SDK project,
sole canonical AIP/Manifest schemas/types/validation tooling.
`atlas-connectors` is one official monorepo, Apache-2.0 by default for Atlas-authored
code, with explicit compatible component exceptions for Ansible/GPL integrations.
Third-party dependencies retain upstream licences/notices.

I0 stages new specification contracts under docs only. Before I1 move schemas
verbatim into SDK, then consume released SDK versions on both sides. No temporary
production duplicate SDK and no remote repository creation in I0. Rights/provenance
review precedes publication/extraction; do not mechanically relabel existing AGPL
SDK/plugin implementation.

## Alternatives considered

A permissively licensed Atlas core contradicts current licence policy. Copied
schemas create competing contracts; a fourth source repo is unnecessary for the
runtime deployment boundary.

## Consequences and validation

Extraction/publishing and exact dependency/licence/SBOM inventory are I1/later
release work. Architecture establishes ownership intent, not a relicensing claim
for existing code or final third-party distribution qualification.

See the [Integration alignment audit](../architecture/integrations/integration-alignment-matrix.md),
[active v1.3 design](../architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md)
and [staged contracts](../architecture/integrations/contracts/README.md).
Implementation status remains in the feature ledger; acceptance of this decision
is not evidence that runtime/catalogue/vendor code exists. Revisit through a
superseding ADR if these authority, execution or ownership boundaries must change.
