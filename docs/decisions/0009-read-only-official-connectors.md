# 0009 — Read-only technical discovery for official v1 Connectors

Status: **Accepted**

Date: 2026-10-11

## Context

Atlas distinguishes technical Assets from operational Services/Business Functions.
Existing evidence/acceptance/graph semantics must not become implicit source write
or business-meaning automation.

## Decision

Official v1 Connectors expose bounded Test Connection and read-only discovery,
with no remediation/change commands. Technical observations never create first-class
Services/Business Functions, choose tenancy, merge sources or infer operational
failure from reachability. Atlas handles acceptance, stable links and absence;
partial/failed/cancelled runs cannot create absence or auto-delete accepted Assets.

Proxmox uses dedicated least-privilege API token only; I4 proves exact calls/ACLs
and dated official/community reference gate/edge-case regressions. Docker uses SSH
keys, documents daemon/group root-equivalent access and logical workload identity,
with no unauthenticated TCP/2375. UniFi is local infrastructure only with documented
local API-key path or validated local read-only fallback; no client-device/cloud
Site Manager discovery. Declarative controls/scopes/facts use Atlas-owned UI.

## Alternatives considered

General Ansible commands/remediation, automatic business objects, client telemetry
and Connector-owned absence/merge policy exceed v1 and require separate decisions.

## Consequences and validation

I4–I6 qualify actual read paths/identity/coverage/source compatibility. I8 audits
source permissions and runtime behavior; read-only declaration alone does not prove
safe executable code. Existing plugin tests remain a compatibility baseline.

See the [Integration alignment audit](../architecture/integrations/integration-alignment-matrix.md),
[active v1.3 design](../architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md)
and [staged contracts](../architecture/integrations/contracts/README.md).
Implementation status remains in the feature ledger; acceptance of this decision
is not evidence that runtime/catalogue/vendor code exists. Revisit through a
superseding ADR if these authority, execution or ownership boundaries must change.
