# Retired Assets and retained discovery history

A source omission is evidence for review, not permission to retire or delete an
Asset. In Reconciliation, review a no-longer-observed item and choose **Retire**
when the Asset is no longer in service. The existing reviewed-version check,
status declaration, Change and audit remain authoritative. Re-observation does
not automatically reactivate a retired Asset. There is no separate Interface
retirement action.

Asset lists (under Filters), Infrastructure Topology and Knowledge Graph offer
**Include retired**. It includes retained records in that view; it is not a
historical point-in-time reconstruction. Retired Asset detail, facts, Changes,
source associations and audit remain available with their existing permissions.
Missing, inactive, unknown and other statuses retain their previous visibility.

An Interface linked to retained discovery history cannot be deleted, even after
removing relationships or disabling its source. The refusal explains this without
exposing source identifiers. If its Asset is out of service, use reconciliation
Retire when available. Retirement does **not** unlock Interface deletion.
Likewise, deleting a source-linked Asset is refused so deletion cannot cascade
away its source identity. Unreferenced manual records remain deletable; automatic
creation assertions alone are not a deletion blocker. Existing relationship
blockers remain in force. This is not a new general Asset tombstone policy.

## API membership and compatibility

`include_retired` is an optional boolean, default `false`, on:

- `GET /api/assets` and `/api/assets/summary`
- `GET /api/topology` and `/api/topology/connectivity`
- `GET /api/operational-graph` and `/api/operational-graph/landscape`

Default collection membership intentionally changes: `status=retired` is excluded
before pagination/counting and graph traversal. Retired nodes, Interfaces exposed
through those nodes and incident edges are absent from current views. A retired
focus returns 404 unless inclusion is requested. Inclusion never bypasses scope
or permissions. Response shapes and direct detail/history routes are unchanged.

Dependency analysis explicitly includes retained providers in its internal graph,
independent of the display filter. Retirement does not erase recorded requirements
or make an incomplete dependency set appear satisfied. Analysis remains a
hypothetical scenario over recorded knowledge, not a live availability claim.

## Persistence and concurrency

No migration or FK change is required. Asset deletion locks and reloads the
canonical Asset before checking source links and deleting. Source linking follows
source → canonical Asset locking and verifies the Asset still exists. A committed
link prevents deletion; deletion that wins first causes linking to refuse without
partial persistence. The Interface source-identity FK remains `ON DELETE RESTRICT`.
Only its specific violation receives the retained-history explanation; unrelated
integrity errors keep the existing generic conflict. Failed deletes roll back the
attempted audit event. Evidence and accepted assertions are never cascaded away to
make an Interface deletable.
