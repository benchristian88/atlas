# 0006 — Official immutable catalogue and protected verified execution

Status: **Accepted**

Date: 2026-10-11

## Context

Current Atlas release packaging provides checksums/informational update checking,
not Connector attestation verification or executable package management.

## Decision

Official source is one Connector monorepo with independent SemVer packages and
immutable GitHub Release assets. Verify exact SHA-256 plus approved repository/
workflow GitHub Artifact Attestations/Sigstore provenance. Manifest trust metadata
supports future explicitly approved publishers, without accepting self-asserted
trust. The archive digest/provenance descriptor is detached from the in-bundle
domain manifest, avoiding a self-referential archive hash.

Atlas releases embed local bootstrap catalogue and qualified Proxmox/Docker/UniFi
bundles for offline first use; installed packages continue offline. Metadata is
checked daily by default; installation/upgrades are explicit admin actions.
Runtime independently verifies exact installed ID/version/digest and fixed
operation. Native root-owned and Docker equivalent protected stores are writable
only by approved installation/update authority; runtime reads/executes only.
No endpoint accepts arbitrary playbook/path/text/Git/Galaxy/command/upload.

## Alternatives considered

Checksum-only authenticity, mutable branch installs, arbitrary community code,
public runtime listeners and runtime-writable stores fail the execution boundary.
Dynamic Galaxy install is not a compatible-baseline update mechanism.

## Consequences and validation

I1 selects verifier/offline proof/archive safety and shell store/catalogue state.
Final qualified offline bundles follow I4–I6 and I8 acceptance. Missing runtime
dependencies produce Runtime update required, never environment mutation. Current
release checksum claims remain accurate and unchanged.

See the [Integration alignment audit](../architecture/integrations/integration-alignment-matrix.md),
[active v1.3 design](../architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md)
and [staged contracts](../architecture/integrations/contracts/README.md).
Implementation status remains in the feature ledger; acceptance of this decision
is not evidence that runtime/catalogue/vendor code exists. Revisit through a
superseding ADR if these authority, execution or ownership boundaries must change.
