# C2.5 — Entity Detail UX Polish

Date: 9 September 2026. **Implemented; live/manual acceptance pending.**
Branch: `feature/c2-5-entity-detail-ux-polish`.
Base HEAD: `4b984aea6deff7515515fe2152ba0531b8d387c9`.
No commit, push, merge, deployment or live acceptance is claimed by this record.

## Delivered scope

Service and Business Function details reuse C2.4 PageHeader, entity marks,
recorded status dots, compact badges, completeness meters and operational card
and theme tokens. Shared detail headers, relationship rows, native disclosure
and sections live in `apps/web/components/entity-detail.js`.

Services show type, managed criticality, recorded status and required knowledge
completeness beside concise identity and actions. Overview retains owner,
technical contact, support group, lifecycle, scope, RTO/RPO and suggested values,
description, documentation and runbook links. Business purpose, providing Assets,
Service dependencies and incoming dependents are separate sections. Dependency
groups show stored requirement, all/any strategy, configured failure effect and
members. Ungrouped dependencies explicitly retain an Unknown consequence.
Creation, requirement/group editing, removal, archive/restore, recovery notes,
completeness actions, history and assertions remain available.

Business Functions retain stored criticality, owner, description, active/inactive
record lifecycle and edit flow. Supporting Service rows can show authorized
criticality, recorded status and completeness from the existing bounded graph
API. Rows initially show six records with native View all disclosure; all
returned links remain available. Optional metadata failure does not hide links.
Counts describe returned authorized relationships. Business Function completeness
is explicitly not evaluated; no availability, health score or derived criticality
is manufactured. Open gaps concern supporting Services, not the Function itself.

Active records deep-link to Knowledge Graph Focus. Service Preview unavailable
opens existing C2.3 analysis within C2.4 Focus. Archived Services/inactive
Functions retain their existing recorded graph disclosure; current operational
Focus excludes these records. No second analysis implementation was added.

## Contained access correction

The audit found existing detail relationship readers checked the starting record
but serialized related names without checking the related entity's view scope.
The existing Service/Business Function read endpoints now use the existing
Principal authorization rules before serializing related records. Business
Function summary counts and Service-gap aggregates respect the corresponding
Service and knowledge-gap scopes. Base Service response counts also scope their
related endpoints; knowledge-gap metadata requires the existing gap permission. Groups with inaccessible members are omitted
as a whole so a partial all/any set is not misrepresented. No hidden member IDs
or hidden member counts are returned. Direct relationships still use their
recorded labels. No frontend filter is treated as an authorization boundary.

No schema, migration, relationship semantics, analysis engine, graph layout or
API shape changes. Fully authorized readers retain all existing data/actions;
restricted readers receive only their authorized relationships. Requests that
finish after navigation or access changes cannot repaint a previous record.

## Automated validation

Executed validation:

- `npm test --prefix apps/web`: 103 passed (including C2.1–C2.4 frontend tests).
- `npm run build --prefix apps/web`: passed; 34 pages generated.
- `apps/api/.venv/bin/python -m pytest apps/api/tests -q`: 273 passed, 3 skipped.
  This includes 28 new detail-access cases, including executed relationship-count
  SQL against minimal SQLite tables. Three PostgreSQL integration cases require
  `ATLAS_TEST_DATABASE_URL` and were skipped; no disposable migrated PostgreSQL
  was configured. Existing framework deprecation warnings remain.
- `.venv/bin/alembic heads` from `apps/api`: unchanged single head `20260909_0015`.
- C2.5 Chrome fixture suite: 30 scenarios passed; no runtime exceptions. Actual
  Service Preview navigation, exit-analysis and Function Focus links passed.
  Light/dark screenshots of both detail pages were visually reviewed.
- Existing C2.4 focused Dashboard/appearance suite passed: Light/Dark at 1600,
  1280, 900 and 390px; explicit theme overrides, System changes, profile saves,
  sidebar, Dashboard and graph inspector surfaces and keyboard focus.
- Existing C2.4 full browser script was attempted and retried, but timed out at
  its graph-inspector Preview action (`check-operations-browser.mjs:233`). The URL
  stayed in Asset Focus without `analysis=unavailable`; no runtime exception was
  reported. This failure remains unresolved. The graph page/inspector code and
  full C2.4 script are unchanged by C2.5. It is not counted as a passing suite.
- `git diff --check`: clean. Relative links in the five changed documentation
  files were checked (37 links; none broken).

Repeat with:

```bash
npm test --prefix apps/web
npm run build --prefix apps/web
apps/api/.venv/bin/python -m pytest apps/api/tests -q
```

From `apps/api`, run `.venv/bin/alembic heads`; expected unchanged single head:
`20260909_0015`.

Serve the production build on localhost port 3125 (`npm run start --prefix
apps/web -- --hostname 127.0.0.1 --port 3125`), then run:

```bash
node apps/web/scripts/check-entity-detail-browser.mjs
ATLAS_BROWSER_DASHBOARD_ONLY=1 ATLAS_WEB_TEST_ORIGIN=http://127.0.0.1:3125 ATLAS_BROWSER_OUTPUT=/private/tmp/atlas-c25-dashboard-regression node apps/web/scripts/check-operations-browser.mjs
```

This fixture-backed Chrome script checks both pages in Light/Dark at 1440, 900
and 390px, header fields, graph/analysis URLs, relationship directions, semantics,
completeness meter accessibility, native keyboard View all, visible focus,
no horizontal page overflow, viewer/denied/missing/empty/unevaluated/inactive
states, optional metadata errors, and Business Function/group edit payloads.
Evidence and screenshots default to `/private/tmp/atlas-c25-browser`.
These synthetic checks are not live-data acceptance.

## Exact live manual acceptance checklist

Use a disposable test environment and manually curated records. Record the
application version, Customer/Site, role, theme and viewport used.

1. Open Dashboard, Knowledge Graph, a populated Service and its Business Function.
   Compare title size, card spacing, entity colors and density in Light and Dark;
   select System and change the OS appearance to confirm it follows.
2. On the Service, compare name, purpose, type, criticality, recorded status,
   lifecycle, owner/contact/support group, scope, RTO/RPO and suggested values,
   description and notes with Edit Service. Open documentation and runbook links.
3. Compare the displayed completeness percentage and required counts with the
   existing summary. Check a never-evaluated Service shows no percentage and an
   evaluated Service with zero requirements shows 100%. Re-evaluate; inspect
   required/recommended gaps, defer, exception/reopen and resolved history.
4. Check Supports links to the correct Business Functions and retains Primary,
   importance and description. Check providing Assets and their recorded labels.
   Open each related entity; use Back to return.
5. Check Depends on contains outgoing Service dependencies and Dependents contains
   incoming ones. Test an optional incoming dependency: it must not say Required
   by. Verify custom source/target labels remain correct.
6. Check required/optional groups with All required and Any one is sufficient,
   all three failure effects and the exact members. Check an ungrouped dependency
   explicitly says its consequence is unknown. Change and reload group semantics.
7. Expand each creation form; add an Asset dependency, a Service dependency, a
   Business Function link and a dependency group. Change an ungrouped requirement.
   Cancel a removal confirmation, then confirm a test removal and verify history.
8. Follow Preview unavailable: the URL must focus the Service with
   `analysis=unavailable`, and the existing graph must explain the scenario.
   Exit analysis, refresh and use Back/Forward. Follow the Business Function
   View in Knowledge Graph action and confirm the correct focus without analysis.
9. On a Business Function with more than six supporting relationships, expand
   View all using Enter/Space; verify every authorized relationship and its count.
   Compare Service metadata with the Service record. Confirm no Function
   operational status or percentage is inferred. Edit and save all existing fields.
10. Check empty providers, dependencies, dependents and supporting Services. Check
    missing/inaccessible IDs and a role without page permission. With separate
    Customer/Site grants, confirm hidden related names, IDs, counts and group
    members are absent from API responses as well as from the page.
11. At desktop, tablet and 390px phone width, Tab through actions, disclosures,
    forms and relationships. Check focus rings, readable status text, meter
    labels, long names/descriptions and no horizontal page scrolling. Repeat
    both themes with expanded forms, gaps and dependency groups.
12. Archive/restore a test Service and deactivate/reactivate a Business Function.
    Verify retained metadata/history and recorded graph remain accessible, current
    Focus/Preview is offered only for active records, and no data is destroyed.

C2.5 remains **not live accepted** until the operator completes this checklist.
Asset/Network detail redesign, network/IP cleanup, richer dependency/Business
Function semantics, enterprise graph work, F1-lite, B2-lite and Homelab Ready
hardening remain deferred.
