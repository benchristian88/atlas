# Homelab Operations Experience (C2.4)

Implementation on the C2.4 feature working tree; live/manual acceptance pending.
See the [validation record](../testing/release-c2-homelab-operations-experience.md).

## Product boundary

The Dashboard answers how the environment is structured and which recorded
knowledge needs attention. The Knowledge Graph presents Business Functions →
Services → Assets as three horizontal lanes. Canonical arrows still follow the
API's source and target: a Service's Supports edge points toward its Business
Function even though the Business Function occupies the left lane.

PostgreSQL remains authoritative. C2.1 builds graph records, C2.2 supplies temporal
dependency-group meaning, and the unchanged C2.3 engine supplies hypothetical
consequences. No new analysis rules, persistence, scores, schema migrations, or
live-health assertions are introduced. Recorded Asset status is lifecycle data;
Service operational status is recorded knowledge, not monitoring.

## Customer and Site viewpoints

The shell selects one accessible Customer and Site, restoring a valid preference
or selecting the first accessible option in the API's deterministic name order.
There is no All Customers or All Sites option. Customers without Sites retain
access to administrative setup; operational pages show a setup state.

Services remain **customer-wide or site-specific**. This is not a tenancy
migration. The explicit implementation decision was to retain those existing
rules: a customer-wide Service can use an authorized provider in another Site;
a site-specific Service still cannot directly acquire a cross-site Asset link.
Site-scoped grants do not acquire customer-wide Service permissions.

The landscape seeds current local Assets and local/customer-wide Services and
Business Functions. One batched expansion of Service relationships adds directly
related authorized providers/context. Remote providers do not seed expansion of
an entire remote Site. Remote entities carry a Site badge. Focus and Find can
follow authorized entities inside the Customer, and analysis can complete
cross-site dependency sets without applying the selected Site as a hard cutoff.
All endpoint and relationship permissions still apply independently.

Customer-wide record forms and Service dependency pickers send the record's
explicit Customer/Site context. Removing the global aggregate viewpoint must not
silently move a customer-wide record into the selected Site or prevent editing
it. These are narrow compatibility adaptations, not entity-detail redesigns.

## Read contracts

| Contract | C2.4 addition | Compatibility |
| --- | --- | --- |
| `GET /api/operational-graph/landscape` | Explicit Customer/Site landscape, existing graph node/edge contracts; empty `focus_key` for Overview | New read-only endpoint |
| `GET /api/operational-graph` | Optional `site_viewpoint=true` uses selected Customer plus per-object authorization across Sites | Default Site-bound behavior unchanged |
| `POST /api/dependency-analysis` | Same opt-in `site_viewpoint=true` before calling the existing C2.3 engine | Scenario/response and engine unchanged |
| `GET /api/dashboard/summary` | Optional `include_customer_wide=true` includes authorized customer-wide completeness/gaps | Default counts unchanged |
| `GET /api/changes` | Optional `include_customer_wide=true` includes authorized customer-wide changes alongside Site changes | Default filtering unchanged |
| Operational graph nodes | Optional Site name, criticality rank, required requirement totals/satisfied counts, interface IP and authorized VLAN | Additive metadata |

The landscape uses the existing builder's temporal edge loading, endpoint batch
loading, group metadata, node serialization, and authorization. It caps output
at 500 nodes and 2,000 relationships and reports truncation without hidden-record
counts. It makes no sequential per-Service graph calls. Find reuses the existing
Assets, Services and Business Functions search endpoints, requesting at most
eight matches of each type and retaining only typed search identity/name in the
presentation. Search is debounced and scoped to the selected Customer.

## Dashboard

`operations-experience.mjs` registers five stable IDs in fixed order:

1. `environment-summary`: Assets, Services, Business Functions, Knowledge Gaps.
2. `environment-overview`: service landscape, All/Critical/With gaps controls,
   navigation directly to graph Focus, and guided empty/partial states.
3. `attention`: unknown effects, ungrouped dependencies, knowledge gaps, and
   high-criticality Services with recorded gaps. An ungrouped dependency is a
   review signal; it is not itself an inferred outage or synthetic gap.
4. `critical-services`: Services with managed criticality rank at least 75
   (the existing high-criticality threshold), bounded to three cards, with a
   View all path, named criticality, accessible recorded status and completeness.
5. `recent-meaningful-changes`: six entries from existing KnowledgeChange data.

Registry entries map to small components in the Dashboard module. The registry
is a future customization seam, not a plugin framework. It provides no layout
persistence, reordering, drag/drop, resizing, catalogue, or customization UI.

Completeness uses the existing `required_satisfied / required_total` presentation
ratio (100% when a successfully evaluated total is zero). Not-evaluated summaries
have no percentage; exceptions remain distinct from naturally satisfied counts.
Business Functions explicitly say completeness is not evaluated. No new score
or completeness evaluator exists.

## Overview, Focus, and Analysis

Relationship and node-type filters project the authorized graph before lane
selection and layout. Focus retains only the component reachable from its focus
through visible edges in either direction, always preserving the focus itself.
Alternative visible paths keep nodes connected. Overview retains genuinely
unlinked records and visible components, but removes records orphaned by filters.
Dependency markers are generated only from surviving visible member edges.
Hidden inspector selections fall back to Focus (or the empty Overview inspector).
Analysis retains its existing overlay context even when relationship lines are
filtered; this visual projection does not change C2.3 analysis or API traversal.


`/knowledge-graph` is Overview. `?focus=service:<uuid>` selects Focus; `depth=2`
expands the backend-bounded neighbourhood. `analysis=unavailable` temporarily
layers the existing C2.3 scenario onto Focus. Exiting analysis retains focus,
depth, and filters. The browser router handles refresh, copied URLs, and history.
The existing `/topology` lenses and focused detail graph contracts remain
reachable for compatibility. Main Knowledge Graph navigation uses the new route.

One click or Enter/Space selects an entity and updates the persistent inspector.
Double click, Find, and explicit Focus actions enter Focus. Find preserves depth
and relationship filters and makes the selected entity type visible. The
inspector can load a bounded one-hop neighbourhood independently without
rebuilding the graph. Assets show interface-backed IP and authorized VLAN;
Service explanations use API reason summaries, group fields and canonical paths.

Small dependency-group buttons are presentation objects keyed from existing
C2.2 group identity. Their subject/member connectors represent the existing
relationships, and their inspector shows requirement, strategy, failure effect,
and visible members. They are never persisted as new operational entities.
Service-to-Service relationships have thinner connectors. Structural Asset
relationships are hidden by default and can be enabled in Filters.

Analysis merges only entities and edges supplied by the C2.3 response into the
visible context, retaining canonical endpoints. Entity colors remain stable.
Unavailable/degraded/unknown use text and solid/dashed borders; unaffected and
unrelated context are subdued. Only API-reported states are shown. Business
Functions never receive derived availability. Runs on never becomes an
Asset-to-Asset propagation rule.

## Presentation, accessibility, and scale

No frontend dependency was added. The audited manifest and lockfile contain
Next/React/React DOM, with no graph library. A fixed deterministic lane layout
uses accessible HTML buttons over SVG connectors, built on the existing graph
normalizer. This avoids adding a layout/library bundle for a single deliberate
layout and keeps Atlas styling, keyboard behavior and SSR boundaries explicit.
The interactive components are client components; URL use has a Suspense boundary.

The target is 20–40 Services, 50–150 Assets, 8–20 Business Functions and hundreds
of relationships. Dashboard shows five items per lane; full Overview/Focus shows
eight initially. Explicit +N controls expand each lane, and a relationship notice
counts connectors attached to collapsed authorized items. A focused visible
entity is retained in the collapsed slice. Full names remain in accessible labels
and the inspector when compact node text wraps to its two-line visual limit.
Server truncation is separately reported; exact omitted server counts are not
invented.

Native scrolling, mouse-drag panning, zoom and Fit keep nodes readable. Fit has an
80% readability floor and resets viewport position; large graphs remain pannable
instead of shrinking into an unreadable thumbnail. Layout is memoized; inspector
selection does not reset zoom/pan. A collapsible semantic relationship list and
independently usable inspector expose names, relationship direction and analysis
paths outside SVG. Controls have labels, nodes have explicit keyboard selection,
focus rings are visible, status has accessible text, and reduced motion is honored.

Semantic colors and compact card/typography primitives work with system light
and dark preference. Desktop uses an adjacent inspector; mobile uses a full-width
inspector below a horizontally scrollable graph. The Dashboard preview remains
pannable and always retains an Open Knowledge Graph action.

## C2.5 entity detail presentation

Service and Business Function details reuse `operations-primitives.js`, PageHeader,
`ops-card`, `ops-badge` and the existing theme tokens. `entity-detail.js` composes
shared breadcrumbs/identity/actions, sections, relationship rows and native
View all/edit disclosures. Styles are scoped to `.entity-detail-page`; Dashboard,
Graph, Asset and Network detail styling is unchanged. CompletenessPanel has an
opt-in compact presentation for Service detail; existing Asset callers retain
their default presentation. Never-evaluated summaries do not display 100%.

Service relationship direction comes from canonical API endpoints and explicit
source/target labels. Dependency groups retain existing requirement, strategy,
failure effect and member identity; ungrouped consequences remain Unknown.
No traversal or inference moves to the frontend. Focus/Preview use `graphHref`.
Existing archived/inactive graph adapters remain available in native disclosure.

Business Functions retain their authoritative criticality and record lifecycle;
no Function availability or completeness score is calculated. Supporting-Service
status/completeness comes from a bounded, authorized one-hop operational graph
read with the record context. All returned relationship rows remain available
through disclosure even when optional graph metadata is unavailable or bounded.

Detail loaders discard stale asynchronous responses. Existing related-entity
read endpoints now filter names/member IDs and Business Function aggregates with
Principal view/gap scopes. Base Service relationship counts also scope their
related endpoints and gate gap metadata. Partially inaccessible dependency groups are omitted
whole so visible subsets are not presented as complete all/any semantics. These
are read-access corrections, not new semantics or a parallel authorization model.
API shapes, writes, graph projection and PostgreSQL schema remain unchanged.

See [C2.5 validation and manual acceptance](../testing/release-c2-entity-detail-ux-polish.md).

## Deferred scope and follow-up

C2.5 Entity Detail UX Polish is implemented before F1-lite. Its live/manual
acceptance remains pending; it adds no major domain semantics.

A post-C2.4 Homelab Ready modeling cleanup should make IP addresses authoritative
on interfaces, with Asset management/primary IP referencing or deriving from an
interface address. Preserve/migrate existing data and update discovery/importers.
C2.4 reads interface IP; it does not use or migrate the duplicated Asset IP field.

Deferred: enterprise graph scale, minimap, alternate layouts, saved perspectives,
automatic Workloads(N) clustering, dashboard customization/drag-drop, named
Dashboards, per-Site layouts, network graph lane/topology mode, Business Function
impact, Asset-to-Asset failure propagation, richer dependency semantics and full
enterprise Impact Analysis. Asset/Network detail redesign remains deferred.
