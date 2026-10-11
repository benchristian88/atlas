# 0003 — Runtime-neutral AIP and isolated Ansible execution

Status: **Accepted**

Date: 2026-10-11

## Context

Atlas already owns scoped knowledge and reconciliation. The worker is a
placeholder; existing SDK `DiscoveryPlugin` protocols do not provide an isolated
execution API. Accepted ADR 0001 preserves PostgreSQL and the derived graph.

## Decision

AIP and `IntegrationRuntime` are runtime-neutral. AnsibleRuntime is the first
implementation, separately deployed with source in the main Atlas repository.
Core never imports Ansible or gains vendor-specific contracts. Runtime failure
must leave the knowledge plane usable. Normal installations include/enabled
runtime with explicit manual-only opt-out. Docker has private Compose networking
and no public runtime port; native/systemd binds loopback with pinned native
Python/Ansible/Collection environment, requiring no Docker/Podman.

Atlas worker/Redis will own dispatch/overlap/retry in I3; PostgreSQL records
schedule/run state. The runtime owns ephemeral execution, not tenancy, acceptance
or scheduling. Add ingestion adapters to existing evidence/assertion/reconciliation
owners. Preserve legacy direct sync separately, never use it for new AIP.

## Alternatives considered

A fourth runtime repository and container-only native deployment add unsupported
packaging/ownership boundaries. Ansible-specific AIP, a second discovery pipeline
and runtime-owned scheduling would duplicate current Atlas semantics.

## Consequences and validation

I1 extends current package/install architecture; I3 adds dispatch and receipt
finalisation. Both deployment methods must pass the same control/AIP contracts,
prove failure isolation and participate in backup quiescence. This extends ADR
0001; it changes no current API/schema/runtime in I0.

See the [Integration alignment audit](../architecture/integrations/integration-alignment-matrix.md),
[active v1.3 design](../architecture/integrations/Atlas_Integration_Architecture_and_Design_Specification_v1.3.md)
and [staged contracts](../architecture/integrations/contracts/README.md).
Implementation status remains in the feature ledger; acceptance of this decision
is not evidence that runtime/catalogue/vendor code exists. Revisit through a
superseding ADR if these authority, execution or ownership boundaries must change.
