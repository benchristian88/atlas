# C2.6 — Usability & Lifecycle Polish

Implementation complete. Automated validation recorded below. **Live/manual
acceptance pending.** No commit, deployment or release acceptance is implied.

## Scope

- Delete mistakes / Archive history for Services and Business Functions, with
  retained tombstones and server-enforced eligibility.
- Organisation, Reference Data, direct Audit Log and System Settings sidebar.
- Permission-filtered URL-based local navigation; supported `/admin/*` deep
  links retained; `/admin` redirects to the first authorized destination.
- General, Backup & Restore, Updates and About on one System Settings page.
  Only existing non-sensitive runtime settings are shown. About explicitly
  labels `apps/web/package.json` metadata as the **Web package version**, not an
  installed-release or commit claim.

See [lifecycle rules and reference audit](../architecture/entity-lifecycle.md).

## Automated validation

Baseline: API **273 passed, 3 skipped**; frontend **103 passed**.

Final validation: **307 API tests passed, no skips; 108 frontend tests passed;
production build passed** (34 static pages plus dynamic routes). **102 browser
scenarios passed**, using production assets and synthetic API fixtures at
1440px, 768px and 390px in light/dark Chrome. Checks include navigation, limited
permissions, redirects, settings empty/safe states, dialog focus in both Tab
directions, Escape/focus return, mobile gutters, deletion redirect, blocker
state and destructive-button WCAG AA text contrast. Screenshots were inspected
for desktop and mobile presentation.

Migration upgrade/downgrade/upgrade preserved all original fields of an existing
Service and archived Business Function; `20260910_0016` is the single head.
Downgrade refusal with retained tombstones passed. `git diff --check` passed.
Dependency deprecation warnings remain from FastAPI/Starlette/Python 3.14;
there were no failed or skipped final API tests.

Commands actually executed:

- API: `ATLAS_TEST_DATABASE_URL=<disposable migrated PostgreSQL> .venv/bin/python -m pytest -q`.
- Frontend: `npm test`; `npm run build`.
- Migration: upgrade from `20260909_0015`, downgrade, upgrade again; compare all
  original Service and inactive Business Function fields; verify one head.
- Browser: `node apps/web/scripts/check-c26-browser.mjs` against a running
  production frontend, with `ATLAS_PLAYWRIGHT_MODULE`, `ATLAS_CHROME_PATH` and
  optional `ATLAS_BROWSER_BASE_URL`/`ATLAS_BROWSER_OUTPUT`. Playwright may be
  installed outside the repository. Uses synthetic API responses; live API
  behavior is covered separately by PostgreSQL tests.
- `git diff --check`.

The PostgreSQL suite exercises actual API creation artefacts, legacy declaration
recognition, automatic gaps, manual knowledge, relationships in both directions,
ended links, dependency groups/memberships, observations/reconciliation,
customer/site denial, Archive/Restore, name reuse, hidden reads/counts, retained
history, rejected tombstone writes, downgrade refusal, and both orderings of a
concurrent reference write/Delete. Race checks wait for an actual PostgreSQL
lock rather than assuming overlap from thread scheduling.

## Manual acceptance checklist

Use a migrated disposable or backed-up test instance and representative accounts.

1. Create a mistaken Service with the minimum required fields. Leave its
   automatic declarations and gaps intact. Verify Delete is enabled, Cancel
   leaves it intact, and confirmation names the Service with permanent-removal
   wording. Confirm deletion and verify it leaves list/search/pickers, Dashboard,
   graph/analysis and Knowledge Gaps. Its old detail URL should be unavailable.
2. Reuse the deleted Service's name and slug. Confirm the new record has a new ID.
   In authorized Audit Log and Changes, verify creation/deletion history remains
   coherent and there is no broken detail link for the deleted target.
3. For separate Services, add a provider, supporting Business Function,
   dependency, dependent or dependency group. Verify Delete is disabled with
   the generic Archive explanation. End a relationship and verify Delete remains
   blocked. Verify later field edits and manual knowledge also block it.
4. Archive a participating Service. Verify existing archive filters, detail and
   historical relationships still work. Restore it and verify Delete stays
   blocked. Confirm Delete and Archive are distinct actions.
5. Repeat mistaken creation/Delete/name reuse for a Business Function. Link a
   Service and verify both entities cannot be deleted. Archive and restore the
   Business Function; existing inactive records should read as archived, retain
   their relationships and never appear as deleted mistakes.
6. With a viewer, confirm lifecycle actions are absent and direct DELETE is
   denied. With a customer/site-scoped manager, confirm out-of-scope IDs return
   404 and blocker explanations disclose no related IDs, names or counts.
7. Open Users, Roles & permissions, Customers and Sites using both sidebar/local
   navigation and old deep links. Organisation stays selected and the matching
   local link has a current-page indicator.
8. Repeat for all five Reference Data pages and their nested knowledge-profile
   links. Confirm existing page functionality is unchanged and permission-limited
   users see only authorized local links.
9. Open Audit Log directly. Open System Settings directly. Neither shows an
   Administration overview or unrelated tab group. `/admin` redirects to the
   first authorized System destination, including for a roles-only account.
10. Check General's safe values/empty state, truthful Backup & Restore and Updates
    planned states, and About's package version label. There must be no secret
    fields, `.env` editor, fabricated release/build data or extra sidebar items.
11. On desktop, tablet and mobile, check both themes, navigation scrolling and
    text wrapping. Keyboard through links and the Delete dialog: Cancel receives
    initial focus, Tab stays in the modal, Escape cancels, and focus returns to
    the Delete button. Verify confirmation buttons have visible focus.
12. Sign off live acceptance separately. Automated passes do not close this gate.

## Deferred to Homelab Ready

Backup/restore engine and validation; version/update checking; About/build
refinement; safe runtime settings; onboarding/first-run flow; optional homelab
starter/template data; Interface-first IP cleanup; install/upgrade, migration,
security and Docker validation; broader browser/mobile/accessibility regression;
release artefacts and documentation/support/compatibility guidance. No unattended
updates, discovery expansion, C3/C4 or enterprise Impact Analysis is part of C2.6.

## Completion repository state

Branch: `feature/c2-6-usability-lifecycle-polish`

HEAD: `b020677d36fef8f2f8c45dceb74a14d17822e5fe`

No commit, push, merge or release was made. No physical deletion was required;
no supported reference type prevented the revised tombstone implementation.

### Material files changed

| File | Purpose |
| --- | --- |
| [README.md](../../README.md) | Update current System navigation and lifecycle guidance. |
| [apps/api/app/database.py](../../apps/api/app/database.py) | Exclude tombstones and automatic artefacts from operational SELECTs. |
| [apps/api/app/models.py](../../apps/api/app/models.py) | Add deleted timestamps and tombstone-aware uniqueness. |
| [apps/api/app/routes/business_functions.py](../../apps/api/app/routes/business_functions.py) | Add lifecycle endpoints and enforce destination scope. |
| [apps/api/app/routes/services.py](../../apps/api/app/routes/services.py) | Identify initial declarations and add scoped deletion endpoints. |
| [apps/api/app/schemas.py](../../apps/api/app/schemas.py) | Define the explicit deletion eligibility response. |
| [apps/api/app/services/knowledge_completeness.py](../../apps/api/app/services/knowledge_completeness.py) | Reject evaluation of deleted Services. |
| [apps/api/app/services/operational_graph.py](../../apps/api/app/services/operational_graph.py) | Exclude tombstones even from inactive focused graphs. |
| [apps/api/tests/test_models.py](../../apps/api/tests/test_models.py) | Update the model contract for deleted_at. |
| [apps/web/app/admin/asset-types/[id]/knowledge-profile/page.js](../../apps/web/app/admin/asset-types/[id]/knowledge-profile/page.js) | Align the existing page context label with its System navigation group. |
| [apps/web/app/admin/asset-types/page.js](../../apps/web/app/admin/asset-types/page.js) | Align the existing page context label with its System navigation group. |
| [apps/web/app/admin/audit/page.js](../../apps/web/app/admin/audit/page.js) | Align the existing page context label with its System navigation group. |
| [apps/web/app/admin/criticality-levels/page.js](../../apps/web/app/admin/criticality-levels/page.js) | Align the existing page context label with its System navigation group. |
| [apps/web/app/admin/custom-fields/page.js](../../apps/web/app/admin/custom-fields/page.js) | Align the existing page context label with its System navigation group. |
| [apps/web/app/admin/layout.js](../../apps/web/app/admin/layout.js) | Render only authorized links within the current System group. |
| [apps/web/app/admin/page.js](../../apps/web/app/admin/page.js) | Replace Administration cards with an authorized redirect. |
| [apps/web/app/admin/relationship-types/page.js](../../apps/web/app/admin/relationship-types/page.js) | Align the existing page context label with its System navigation group. |
| [apps/web/app/admin/roles/page.js](../../apps/web/app/admin/roles/page.js) | Align the existing page context label with its System navigation group. |
| [apps/web/app/admin/service-types/[id]/knowledge-profile/page.js](../../apps/web/app/admin/service-types/[id]/knowledge-profile/page.js) | Align the existing page context label with its System navigation group. |
| [apps/web/app/admin/service-types/page.js](../../apps/web/app/admin/service-types/page.js) | Align the existing page context label with its System navigation group. |
| [apps/web/app/admin/system-settings/page.js](../../apps/web/app/admin/system-settings/page.js) | Provide safe General settings and planned Backup/Updates plus About. |
| [apps/web/app/admin/users/page.js](../../apps/web/app/admin/users/page.js) | Align the existing page context label with its System navigation group. |
| [apps/web/app/business-functions/[id]/page.js](../../apps/web/app/business-functions/[id]/page.js) | Expose Archive/Restore and shared Delete confirmation. |
| [apps/web/app/business-functions/page.js](../../apps/web/app/business-functions/page.js) | Present existing inactive Business Functions as archived. |
| [apps/web/app/globals.css](../../apps/web/app/globals.css) | Keep System navigation compact and modal layout/contrast accessible. |
| [apps/web/app/services/[id]/page.js](../../apps/web/app/services/[id]/page.js) | Expose shared Delete eligibility/confirmation beside existing lifecycle. |
| [apps/web/components/admin-sections.js](../../apps/web/components/admin-sections.js) | Retain a compatibility export for shared System definitions. |
| [apps/web/components/navigation-icon.mjs](../../apps/web/components/navigation-icon.mjs) | Use existing icon family for the four System groups. |
| [apps/web/lib/navigation-model.mjs](../../apps/web/lib/navigation-model.mjs) | Use the new System group definitions. |
| [apps/web/tests/navigation-model.test.mjs](../../apps/web/tests/navigation-model.test.mjs) | Update navigation regression expectations to the approved grouping. |
| [apps/web/tests/ui-polish.test.mjs](../../apps/web/tests/ui-polish.test.mjs) | Verify the retired Administration landing route redirects. |
| [docs/admin/service-types-and-criticality.md](../admin/service-types-and-criticality.md) | Point operators to Reference Data. |
| [docs/architecture/service-model.md](../architecture/service-model.md) | Link the new lifecycle policy. |
| [docs/decisions/README.md](../decisions/README.md) | Index the new decision. |
| [docs/product/development-roadmap.md](../product/development-roadmap.md) | Place C2.6 before F1-lite/B2-lite and preserve hardening work. |
| [docs/product/feature-ledger.md](../product/feature-ledger.md) | Record implemented capabilities separately from planned placeholders and acceptance. |
| [docs/product/release-c2-plan.md](../product/release-c2-plan.md) | Record C2.6 delivery and the remaining Homelab Ready sequence. |
| [apps/api/app/services/entity_lifecycle.py](../../apps/api/app/services/entity_lifecycle.py) | Enforce creation-only eligibility and transactional deletion with retained history. |
| [apps/api/migrations/versions/20260910_0016_entity_tombstones.py](../../apps/api/migrations/versions/20260910_0016_entity_tombstones.py) | Add lifecycle fields, indexes, concurrent-write guards and safe downgrade refusal. |
| [apps/api/tests/test_entity_lifecycle_postgres.py](../../apps/api/tests/test_entity_lifecycle_postgres.py) | Exercise real API, history, scope, reference and race behavior. |
| [apps/web/components/entity-delete-action.js](../../apps/web/components/entity-delete-action.js) | Share eligibility, permanent-removal wording and keyboard-safe confirmation. |
| [apps/web/lib/system-navigation.mjs](../../apps/web/lib/system-navigation.mjs) | Keep grouped routes, permissions and active states in one definition. |
| [apps/web/scripts/check-c26-browser.mjs](../../apps/web/scripts/check-c26-browser.mjs) | Run opt-in production Chrome layout/permission/keyboard regressions. |
| [apps/web/tests/system-lifecycle.test.mjs](../../apps/web/tests/system-lifecycle.test.mjs) | Test System group authorization, settings and shared lifecycle UI contracts. |
| [docs/architecture/entity-lifecycle.md](../architecture/entity-lifecycle.md) | Record exact eligibility, schema audit, concurrency and API behavior. |
| [docs/decisions/0002-mistaken-entity-tombstones.md](../decisions/0002-mistaken-entity-tombstones.md) | Record the approved tombstone decision without rewriting ADR 0001. |
| [docs/testing/release-c2-usability-lifecycle-polish.md](release-c2-usability-lifecycle-polish.md) | Record validation, manual acceptance and the completion report. |

### Git status

`git status --short`:

```text
 M README.md
 M apps/api/app/database.py
 M apps/api/app/models.py
 M apps/api/app/routes/business_functions.py
 M apps/api/app/routes/services.py
 M apps/api/app/schemas.py
 M apps/api/app/services/knowledge_completeness.py
 M apps/api/app/services/operational_graph.py
 M apps/api/tests/test_models.py
 M apps/web/app/admin/asset-types/[id]/knowledge-profile/page.js
 M apps/web/app/admin/asset-types/page.js
 M apps/web/app/admin/audit/page.js
 M apps/web/app/admin/criticality-levels/page.js
 M apps/web/app/admin/custom-fields/page.js
 M apps/web/app/admin/layout.js
 M apps/web/app/admin/page.js
 M apps/web/app/admin/relationship-types/page.js
 M apps/web/app/admin/roles/page.js
 M apps/web/app/admin/service-types/[id]/knowledge-profile/page.js
 M apps/web/app/admin/service-types/page.js
 M apps/web/app/admin/system-settings/page.js
 M apps/web/app/admin/users/page.js
 M apps/web/app/business-functions/[id]/page.js
 M apps/web/app/business-functions/page.js
 M apps/web/app/globals.css
 M apps/web/app/services/[id]/page.js
 M apps/web/components/admin-sections.js
 M apps/web/components/navigation-icon.mjs
 M apps/web/lib/navigation-model.mjs
 M apps/web/tests/navigation-model.test.mjs
 M apps/web/tests/ui-polish.test.mjs
 M docs/admin/service-types-and-criticality.md
 M docs/architecture/service-model.md
 M docs/decisions/README.md
 M docs/product/development-roadmap.md
 M docs/product/feature-ledger.md
 M docs/product/release-c2-plan.md
?? apps/api/app/services/entity_lifecycle.py
?? apps/api/migrations/versions/20260910_0016_entity_tombstones.py
?? apps/api/tests/test_entity_lifecycle_postgres.py
?? apps/web/components/entity-delete-action.js
?? apps/web/lib/system-navigation.mjs
?? apps/web/scripts/check-c26-browser.mjs
?? apps/web/tests/system-lifecycle.test.mjs
?? docs/architecture/entity-lifecycle.md
?? docs/decisions/0002-mistaken-entity-tombstones.md
?? docs/testing/release-c2-usability-lifecycle-polish.md
```
