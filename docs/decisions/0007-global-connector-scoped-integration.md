# 0007 — Global one-version packages and scoped connection lifecycle

Status: **Accepted**

Date: 2026-10-11

## Context

Existing Integration/DiscoveryRun are Customer/Site scoped; there is no installed
Connector state. Existing scoped grants cannot authorize instance-global executable
package changes.

## Decision

Package install/update/rollback/uninstall and mappings are instance-global,
global-admin-only. Each Connector has one active version per Atlas instance;
Integration instances remain Customer/Site scoped, one per source endpoint/controller.
Every run records exact version/digest. Updates validate all dependent Integrations'
config, credential presence, mappings and runtime before activation. Missing
requirements keep current version active and show Update requires configuration.
Secrets never return to browser during validation.

Disable reversibly pauses dispatch while preserving config/credentials/history;
it creates no absence. Remove destroys credentials/retires live schedule/connection
while retaining runs/evidence/provenance/source links/accepted knowledge. Block
uninstall while any live connection uses the package, including disabled ones.
Uninstall removes executable code only. Historical retired references do not block
uninstall. Rollback is catalogue-driven reinstall of a prior compatible immutable
version, preserving every historical execution identity.

## Alternatives considered

Per-tenant executable installation, side-by-side active versions and destructive
uninstall add avoidable security/history complexity. Blind version activation or
secret rehydration violates the update/config boundary.

## Consequences and validation

I1 adds global shell state, I2 adds mapping/config/update validation, I3 guards
in-flight jobs and retirement. Existing authorization service and run lifecycle
remain authoritative; I0 adds no permissions/migrations or user flow.

See the [Integration alignment audit](../architecture/integrations/integration-alignment-matrix.md),
[active v1.3 design](../architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md)
and [staged contracts](../architecture/integrations/contracts/README.md).
Implementation status remains in the feature ledger; acceptance of this decision
is not evidence that runtime/catalogue/vendor code exists. Revisit through a
superseding ADR if these authority, execution or ownership boundaries must change.
