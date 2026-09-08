# Explainable dependency analysis

Status: C2.3 implemented; subsequent live LXC acceptance complete for its lean scope.
See the [validation and acceptance record](../testing/release-c2-explainable-dependency-analysis.md)
for separate implementation-time automated evidence and later live results.

`POST /api/dependency-analysis` derives hypothetical Service consequences from
accepted current knowledge. It does not report live health or write scenario,
analysis, operational state, assertions, dependencies, or discovery records.
PostgreSQL remains the source of truth; no migration or infrastructure is added.

## Input and versioned output

```json
{
  "focus_type": "asset",
  "focus_id": "<asset UUID>",
  "state": "unavailable",
  "max_depth": 8,
  "max_results": 100,
  "max_paths_per_result": 3
}
```

Focus may be `asset` or `service`; the only scenario state is `unavailable`.
Unknown input fields, historical `as_of`, other states and out-of-range limits
are rejected with 422. No new permission keys are introduced.

The response includes `schema_version=1`, `engine_version=c2.3-v1`, `focus_key`,
compact `focus` identity, `analysis_time`, `scenario_state`, an explicit scenario
`assumption`, `truncated`, safe `warnings`, and `results`.

Each result contains compact Service identity (`key`, `entity_id`, `name`,
`href`), `state`, `classification`, `distance`, `reasons`, and `paths`. Reasons
identify the group or ungrouped edge, strategy, requirement, failure effect,
satisfaction, consequence, reason code, triggering edge keys, and all visible
members with their derived states and full canonical C2 graph edges. Additive
summary text is for readability; structured fields are authoritative.

Paths embed their compact nodes and complete edges, so a result limit never
creates a path referring to an omitted intermediate result. Path nodes run from
the scenario toward the consequence, while every edge retains canonical
**dependent Service → provider** direction. C2.4 can use these stable identities
for highlighting and “why?” interactions without reverse-engineering prose.

## Evaluation and assumptions

Only `service_asset` and `service_service` edges participate. Relationship Type
names, Required/Optional and `required_for_operation` do not create extra
inference rules. No Asset→Asset or Business Function outage rule is introduced.

The hypothetical baseline assumes members remain available unless this scenario
derives a consequence for them. Persisted operational status is not monitoring
input. Results describe the caller's authorized knowledge and workspace scope,
not an exhaustive claim about dependencies outside that scope. `unaffected`
means unaffected by this scenario under those assumptions, not healthy in reality.

| Strategy | Satisfied | Unsatisfied | Unresolved |
| --- | --- | --- | --- |
| `all` | Every member is unaffected | At least one member is unavailable | No unavailable member, but a degraded/unknown member exists |
| `any` | At least one member is unaffected | Every member is unavailable | No unaffected alternative and at least one degraded/unknown member |

An unsatisfied set applies its explicit effect: unavailable, degraded or unknown.
An unresolved set yields unknown: lean semantics cannot establish whether a
degraded or unknown Service still satisfies its dependants. A satisfied set has
no consequence. Ungrouped edges retain C2.2's null strategy and unknown effect;
an unavailable ungrouped dependency therefore produces unknown, even if Required.
An Optional set with degraded effect produces degraded when unsatisfied.

Independent sets aggregate with this precedence:

```text
explicit unavailable > unknown > explicit degraded > unaffected
```

An explicit outage condition suffices for unavailable. Otherwise uncertainty
could conceal a stronger consequence and takes precedence over degradation.

The engine computes two deterministic monotone closures:

1. Seed the focus unavailable. Repeatedly add Services whose sets explicitly
   establish unavailability, until stable.
2. Hold those unavailable states fixed. Derive degraded/unknown consequences
   until stable. Other states can only advance unaffected → degraded → unknown.

At most `N+1` and `2N+1` passes respectively are needed for `N` candidate Services.
This avoids retaining a transient unknown when a later unavailable member makes
an explicit degraded effect conclusive. Legitimate cycles terminate; they are
not rejected. Cycles without a scenario-supported unsatisfied condition do not
invent failures. Cycle edges remain in reasons; displayed paths are simple and
never loop. Ordering uses stable node/group/edge keys, never names or row order.

A Service is returned only when an affected dependency gives it a relevant
reason. A shielded `any` set may produce an unaffected result; that result does
not propagate. Unrelated Services and the scenario focus are not result rows.
A shortest causal path of one edge is direct; longer is downstream. A satisfied
set cannot create a misleading direct shortcut to an independently affected
Service. Distance is explanation length, not severity.

## Graph acquisition and limits

`DependencyAnalysisEngine` uses `OperationalGraphBuilder`'s internal completion
profile, not a second graph loader. The profile traverses incoming dependencies,
then includes outgoing sibling members of reached Services to evaluate `any`
correctly. The generic C2.1 graph API and C1 adapters remain unchanged.

All times use one captured clock value. Ended/future dependencies, groups and
memberships follow the C2.1/C2.2 current-valid rules. Ending group membership
removes its semantics; a still-current underlying dependency remains ungrouped.

Safety limits are explicit:

- graph acquisition: 20 incoming hops plus a boundary probe, 2,000 nodes and
  5,000 edges, followed by bounded member completion;
- response `max_depth`: explanation paths, default 8, allowed 1–20;
- `max_results`: default 100, allowed 1–500;
- `max_paths_per_result`: default 3, allowed 1–20.

Acquisition depth is independent of response path depth. This prevents a short
requested explanation depth from silently treating a later-affected alternate
as available. At graph limits, input sets or cycles may be incomplete: return
`truncated=true`, a warning and **no conclusions**. At output limits, return only
complete bounded paths with `truncated=true`; never imply exhaustive results.
The path search keeps at most the requested count plus one per node to detect
truncation and avoids unbounded all-path enumeration.

## Authorization and presentation

Focus uses the shared builder's normal non-disclosing 404. Every edge and
endpoint must pass existing permission/scope checks before graph membership.
Global callers are pinned to the focus customer; active site restrictions and
site grants remain authoritative. Hidden intermediates cannot connect visible
partial paths. Hidden names, IDs, edge/group metadata and counts are not returned.
Reasons contain only projected, authorized current members. The builder privately
marks sets with unavailable-to-the-caller members as incomplete. If an `any` set
has no visible available alternative but is incomplete, the engine returns
unknown rather than claiming that every member failed. The response includes no
hidden identities, membership counts or private completeness marker. An `all`
set can still be unsatisfied by a visible unavailable member; a visible available
`any` alternative can still satisfy its set. The scope assumption applies to all
conclusions.

Viewers can run a preview with existing view permissions; no manage permission
or accepted-state mutation is required. The minimal panel appears on Asset and
active Service details with dependency view permission. It displays textual
states, requirements, group names, reason summaries, member states and paths,
plus empty/error/truncation messages. Switching focus or workspace resets it.

C2.4's dashboard/graph redesign, full Impact Analysis, Business Function impact,
Asset→Asset failure propagation, minimum/quorum, confidence scoring, recovery
analysis and change simulation remain deferred.
