# 0008 — Exact global taxonomy mapping and declared namespaced facts

Status: **Accepted**

Date: 2026-10-11

## Context

Managed AssetType/RelationshipType have stable keys, activity and reference
lifecycle. Legacy sync silently registers missing keys. Fact storage/predicates
exist, but no manifest fact metadata registry or version-global Connector mapping.

## Decision

Manifests declare source object classes and recommended Asset Type keys, and
source relationship semantics with recommended Relationship Type keys/direction.
Atlas silently maps only exact active compatible stable keys. Unresolved/new classes
block activation until global admin maps existing type or creates one through the
normal managed workflow; ignore only explicitly optional classes. Mapping is per
installed Connector version and inherited by every Integration, without overrides.
A new unresolved update class cannot activate; Connectors create no taxonomy.

Networks/Interfaces/status/identity remain canonical AIP fields. Namespaced facts
declare type/class/label/cardinality/applicable classes. New fact classes are
descriptive and never acceptance authority; retain existing observed/declared/
intended/inferred distinctions. New AIP bypasses legacy direct-sync auto-registration
by using existing evidence/reconciliation ownership with additive adapters.

## Alternatives considered

Fuzzy display-name matching, per-Integration mapping and hidden canonical fact
aliases create inconsistent knowledge. Executable expressions and arbitrary
frontend assets are not needed for bounded declarative forms/scopes.

## Consequences and validation

I2 implements mappings and update gates; I3 extends predicate/fact/reference
handling deliberately. Preserve current reference-data FKs/activity/applicability,
legacy sync tests and manually accepted knowledge. I0 implements only contracts.

See the [Integration alignment audit](../architecture/integrations/integration-alignment-matrix.md),
[active v1.3 design](../architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md)
and [staged contracts](../architecture/integrations/contracts/README.md).
Implementation status remains in the feature ledger; acceptance of this decision
is not evidence that runtime/catalogue/vendor code exists. Revisit through a
superseding ADR if these authority, execution or ownership boundaries must change.
