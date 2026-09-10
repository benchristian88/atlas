# Service and Business Function lifecycle

C2.6 applies **Delete mistakes. Archive history.** See
[ADR 0002](../decisions/0002-mistaken-entity-tombstones.md).

## Product behavior and API

Delete permanently removes a mistaken entity from the operational model. It
sets `deleted_at`, preserves the underlying row and history, and records
`service.deleted` / `business_function.deleted` audit events and corresponding
`*_deleted` Changes with name snapshots. There is no user-facing restore.

The existing Service `services.archive` permission authorizes both lifecycle
actions; Business Functions use `business_functions.manage`. Eligibility and
Delete both enforce object customer/site scope, with 404 for hidden targets.
No new role grants or permissions are necessary. Scope is rechecked after the
deletion lock is acquired. Business Function update also validates permission
on the destination site when changing scope.

Additive endpoints:

- `GET /api/services/{id}/deletion-eligibility`
- `DELETE /api/services/{id}`
- `GET /api/business-functions/{id}/deletion-eligibility`
- `DELETE /api/business-functions/{id}`
- `POST /api/business-functions/{id}/archive`
- `POST /api/business-functions/{id}/restore`

Eligibility returns `{eligible, reason}`. No blocker counts, category names,
related IDs or related names are disclosed. A stale eligible client receives
409 if operational participation has since occurred. A deleted target is 404.

Service Archive/Restore and archive list filters retain their existing behavior.
Business Function Archive maps to existing `active=false`, Restore to
`active=true`; existing inactive records are presented as archived. Existing
`active_only` and default inclusive list behavior remain compatible. Archived
records remain accessible for history and cannot be deleted. Restoring an
archived record does not erase participation history or make it a mistake.

## Exact eligibility rule

An entity must be undeleted, unarchived/active, and have equal original
`created_at` and `updated_at` values. This also blocks later field edits that
were not represented by a per-field assertion.

The following block deletion:

- Any FK reference to the entity, without filtering temporal validity. Current,
  future and ended provider links, Service dependencies in either direction,
  Service–Business Function links and dependency groups all count.
- Any entity audit other than its creation audit; any entity Change other than
  creation or supported automatic completeness changes. Even otherwise
  automatic Changes block if tied to an assertion, discovery run or
  reconciliation item.
- Any run-observation or reconciliation entity reference.
- Any assertion referencing the entity as subject or object, except a verified
  original Service declaration batch. Retracted, superseded, observed or
  manually added assertions beyond that batch block.
- Any gap with a manual resolution, exception, deferral or assignment, or an
  audit event targeting one of the entity's retained gaps.

Original Service declarations are identified by the server-recorded initial
assertion IDs on new creation audit events. For pre-C2.6 records, the declaration
must share the entity's original PostgreSQL transaction creation timestamp and
have been first observed before its `service_created` Change. In both cases,
only one assertion per supported initial predicate is allowed; its value must
match the current field. It must still be confirmed, accepted, declared,
unretracted and unsuperseded, without an evidence/run/object reference or ended
validity, and its first/last observation and acceptance times must agree.

Automatic gaps and completeness summaries alone do not block. Automatic Change
exceptions are `service_completeness_changed`, `knowledge_gap_opened`,
`knowledge_gap_resolved` and `knowledge_requirement_changed`, in addition to
creation. Repeated automatic evaluation therefore does not force Archive.
No history is physically removed.

## Reference audit

| Persisted record | Treatment |
| --- | --- |
| `service_asset_dependencies` | Any row blocks, including ended links. |
| `service_dependencies` | Both source and target block, including ended links. |
| `service_business_functions` | Either entity blocks, including ended links. |
| `dependency_groups` | Any parent Service reference blocks. |
| `dependency_group_memberships` | Reachable only through a retained group/dependency; those parents already block. |
| `knowledge_assertions` | Check both subject and object; only verified initial declarations are exempt. |
| `knowledge_changes`, `audit_events` | Preserve snapshots; only creation/automatic exceptions above are allowed. |
| `knowledge_gaps`, `knowledge_completeness_summaries` | Preserve automatic artefacts, hide them operationally; manual gap decisions block. |
| `run_observed_entities`, `reconciliation_items` | Any canonical entity reference blocks. |
| `evidence_records` | No Service/BF FK or canonical entity UUID field; actual associations are via assertions/observed entities, which block. External source identifiers alone are not canonical entity references. |
| `entity_source_links` | Current schema permits Assets only, with an Asset FK; no Service/BF source-link capability exists. |
| `documents` | Current persistence/generator is Asset-only, with `asset_id`. No supported Service/BF generated-document reference exists. Future F1/C4 associations must extend this policy. |
| Asset relationships, interfaces, custom fields | Asset-bound; no first-class Service/BF reference. |

No supported reference type required physical deletion or destruction of history.
Free-text resemblance to an entity name is not treated as an authoritative link.

## Read and concurrency boundaries

SQLAlchemy's shared SELECT policy excludes Service/BF tombstones and their
assertions, gaps and completeness summaries, including scalar/count queries.
Audit and Changes remain visible under their existing authorization; entity
links disappear when their target is deleted. `include_deleted=True` is an
internal execution option only. Graph viewability also rejects tombstones even
when an inactive focus is requested. Completeness evaluation explicitly rejects
a deleted Service object, including one already loaded in a session.

Delete locks and refreshes the entity using `FOR UPDATE` before checking all
references. PostgreSQL triggers acquire `FOR SHARE` on canonical Service/BF
references for relationship, group, assertion, observation, reconciliation,
completeness, audit and Change writes. A concurrent writer either completes
before the eligibility check or waits and rejects the deleted target. Entity
updates cannot modify an existing tombstone. Deletion audit/Change writes are
the explicit historical exception. Integrity errors use the existing 409
response handling. No new worker or secondary persistence is introduced.

Migration `20260910_0016` adds nullable timestamps and rebuilds name/slug unique
indexes to exclude tombstones. Existing rows are not rewritten. Business
Function archived-name uniqueness is unchanged. Downgrade works while no
tombstones exist and fails transactionally once any exist, preserving state
instead of silently resurrecting records.
