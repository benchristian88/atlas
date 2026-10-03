# Showcase Networks-off and singleton correction

> Historical acceptance record. Layout descriptions and measurements below are
> superseded by [shared Connectivity geometry](showcase-shared-geometry.md).

Presentation-only correction on `feature/topology-showcase`, based on
`b5d1aa58137ce10c1fd95bc9dae9c8928af22967`. No migration, persisted data, API,
authorization, Platform, Connectivity, aspect-selection or layout-engine change.
The existing icon/name tiles and progressive collapse remain intact.

## Behavior (A–H)

Previously Showcase added Network nodes referenced by membership edges, attached
those Networks to Asset branches, and rendered dashed membership connectors.
It now follows backend Connectivity's `show_networks=False` eligibility rule:
only Asset nodes and accepted structural edges between those Assets. The existing
`membership` edge kind and durable Asset keys provide classification. No display
name, VLAN name, vendor or IP heuristic is used. There is no shared cross-language
filter helper to call; the Python query and traversal remain unchanged.

Filtering precedes parentage, grouping and layout, eliminating Network-only space
reservations and neighbour signatures. Gateway, switch, host and other device
Assets remain, including an Asset named `Default` in a regression test. Logical
Networks named `Default`, `Apps VLAN` and `IoT VLAN` do not appear.

A single eligible workload remains a direct tile under its actual host. Two or
more eligible members retain their host-local category group; no cross-host merge
occurs. Workload totals are removed from category footers. Collapsed categories
retain truthful +N. Endpoint Type groups retain their device totals. Removing the
empty footer from fully visible categories is the only geometry adjustment.

## Acceptance and validation (I–O)

The 44-Asset reference includes three logical Networks and 44 interface-membership
edges. Its Showcase is identical to the same input with those Networks and
memberships removed. All 44 Assets remain represented, at 1920×1080 and scale 1.
Category wrappers fall from 14 to five, with singleton workloads shown directly.
The larger 50-Asset shape also remains complete at native-scale 16:9.

Compared the previous reference screenshot with the new scene at
`/tmp/atlas-showcase-networks-off/reference-light-scene.png`. Visually confirmed
no logical Network nodes or dashed membership connectors, intact device/hosting
branches, direct singleton tiles, compact multi-member groups and no workload
footer totals. Also inspected the collapsed category crop showing +96 without a
redundant total. Production data was not accessed.

| Command | Result |
| --- | --- |
| `node --test tests/showcase.test.mjs` (`apps/web`) | 18 passed. |
| `npm test` (`apps/web`) | 233 passed, none skipped. |
| `.venv/bin/pytest -q tests/test_infrastructure_topology.py` (`apps/api`) | 16 passed, including Networks on/off behavior. |
| `npm run build` (`apps/web`) | Passed; all 38 pages generated. |
| `node scripts/check-showcase-browser.mjs` (`apps/web`) | Nine scenarios passed; source VLAN/membership exclusion, singleton/multiple groups, no workload totals, truthful +N, no metadata, offline PNGs, preview/export parity and Platform before/after. No page errors. |
| `node scripts/check-infrastructure-topology-browser.mjs` (`apps/web`) | Six scenarios passed: light/dark at 1440, 1100 and 800px. Platform behavior and Connectivity Networks toggle, traversal, filters, selection and routing remain unchanged. |
| `git diff --check` | Clean. |

Adaptive fixtures occupy less space after singleton removal. Existing aspect
selection is unchanged; updated fixtures still exercise adaptive, near-maximum
and genuinely oversized cases. No user knowledge is edited by any browser check.

## Files and repository state (P)

`apps/web/lib/showcase.mjs` applies eligibility and singleton rules;
`apps/web/components/showcase.js` removes membership styling and category totals.
The fixture, unit test and browser acceptance files cover the reduced projection.
The operator guide, architecture guide and feature ledger describe current
behavior; the previous compact-poster record is retained as historical evidence.
No commit or push. Final `git status --short` is included in the completion response.
