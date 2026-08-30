# Knowledge completeness architecture

Current baseline: implemented for Assets and Services. The original v1 Asset
foundation described below was extended by Release C1 using the same requirement,
gap, summary, and evaluator concepts.

Atlas separates three kinds of knowledge state:

- Accepted operational records (`Asset`, `AssetInterface`, and `AssetRelationship`) describe the current working model.
- Assertions, evidence, and reconciliation explain provenance and resolve competing observations.
- Knowledge requirements and gaps describe knowledge that is absent, stale, or insufficient. A gap never deletes an asset and is not a reconciliation item.

## Data model

`KnowledgeRequirementDefinition` stores database-driven, non-executable rules. A null `asset_type_id` is global; otherwise the immutable Asset Type UUID anchors a type profile. Human-readable type and relationship names are resolved at read time, so renames do not break rules. References use restrictive foreign keys and are validated before persistence.

`KnowledgeGap` stores the lifecycle of a failed rule for an entity. A PostgreSQL partial unique index permits only one active (`open`, `deferred`, or `exception`) gap for a requirement/entity pair while retaining resolved and superseded history.

`KnowledgeCompletenessSummary` is the current one-row-per-entity projection used by asset lists and dashboards. It reports counts and a status rather than presenting a percentage as the sole indicator.

All three use Atlas's Python `uuid4` model convention and PostgreSQL `gen_random_uuid()` server defaults. Migration `20260720_0012` is additive.

## Evaluation

The deterministic evaluator loads active global requirements plus the profile for the asset's current Asset Type. It validates each structured rule, evaluates current operational state, opens or updates one gap, resolves satisfied gaps, supersedes no-longer-applicable gaps, processes expired exceptions/deferrals, and refreshes the summary in one transaction.

Direct mutations use a database savepoint. An unexpected evaluator defect leaves the valid operational edit intact and records `not_evaluated` rather than false completeness. Profile-wide reevaluation is bounded; no new broker or background system is introduced.

Statuses are:

- `critical_gaps`: an open critical required/conditional gap.
- `incomplete`: another required/conditional gap is open.
- `operationally_complete`: only recommended gaps remain.
- `exception_accepted`: required knowledge has no open gap but an active exception remains.
- `complete`: no open gaps or exceptions.
- `not_evaluated`: no successful evaluation exists.

Recommended gaps do not make an asset operationally incomplete. Non-expired exceptions are counted as excepted, not naturally satisfied.

## Rules and lifecycle

Supported rules are `field_present`, `field_value_in`, `custom_field_present`, `custom_field_value_in`, `interface_exists`, `interface_has_ip`, `relationship_exists`, `relationship_target_type`, `minimum_relationship_count`, `minimum_interface_count`, bounded `one_of`, `explicit_state_or_exception`, and `freshness_within_days`. Rules support minimum counts, relationship direction, allowed endpoint Asset Types, `unless`, and conservative `applicable_when` conditions. `owner_exists` is recognized but deliberately disabled until Atlas has an ownership model.

Exceptions require a reason and may expire. Deferrals require a reason and may have a review time. Expiry reopens the gap. State transitions create meaningful `KnowledgeChange` rows; unchanged reevaluation creates no timeline noise. Configuration actions remain independently auditable.

The generic entity type/ID boundary and
`get_entity_completeness_context()` now support Assets and Services. Business
Function completeness remains unimplemented. Future analysis may use scoped
gaps and exceptions as qualifiers, but completeness is not Impact Analysis and
does not prove health, outage behavior, protection, or recoverability.
