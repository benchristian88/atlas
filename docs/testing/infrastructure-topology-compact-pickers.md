# Infrastructure Topology compact presentation controls

21 September 2026. Presentation-only polish, validated with isolated browser API
fixtures and the existing disposable PostgreSQL database. No live Atlas records
were changed. This supplements the [presentation identity validation](infrastructure-topology-identity.md).

## A–C: Repository

- Branch: `feature/infrastructure-topology-v0`.
- HEAD: `7ec0812d0e9a4048f510617f593159c93a850b99`.
- Started with a clean working tree. No branch change, commit, push or merge.
- Final `git status --short` is recorded below.

## D–M: Implementation and acceptance

| Area | Result |
| --- | --- |
| Topology context | Removed the single context-line renderer inside the shared ExpandedGraphSurface content. Overview, Platform, Network & VLAN and Connectivity all omit it, including expanded mode. Removed its unused CSS. Global Customer/Site context, page heading and existing descriptions remain. |
| Shared picker | Both existing `presentationField` consumers continue using one `PresentationPicker`. Its internal `PresentationChoice` renders the same accessible menu interaction for Icon and Accent. No page-specific option arrays or picker implementations. |
| Existing primitives | Reuses CrudScreen's custom field hook, `form-grid`, `field`, PresentationIcon/NavigationIcon, existing account-dropdown/item styles and AccountMenu's button/menu interaction pattern. There was no generic popover primitive to consume. No new dependencies. |
| Icon | Collapsed button shows the current icon, readable registry label and chevron. Two-column menu retains all 14 registry options, with selected checkmark and `aria-checked`. |
| Accent | Collapsed button shows a theme-aware swatch, name and chevron. Two-column menu retains all ten accents, readable labels and selected checkmark. Existing identity tokens are unchanged. |
| Preview and copy | Small icon/name preview updates immediately for name, icon or accent changes. Helper copy is “Used for topology presentation only.” |
| Asset Categories | Add/Edit continue storing the existing icon_key/accent_key values. Active, topology visibility, validation and protected Uncategorized behavior remain in the existing form/routes. Browser acceptance covers edits, save/reload, custom-category creation and existing Reference Data lifecycle cases. |
| Networks | Same picker in Add/Edit, preserving all other fields and existing permission checks. Browser acceptance covers initial Network/Blue defaults, edits, save/reload and custom Network creation. |
| Accessibility | Visible labels; native buttons; `aria-haspopup`, `aria-expanded` and selected state; selected option receives focus on opening; arrow keys, Home/End, Enter/Space; Escape and selection return focus; Tab/Shift+Tab continue through the form; outside click/blur dismiss. Choice never depends on colour alone. |
| Themes/layout | Light/dark at 1440, 1100 and 800px. Controls share the existing two-column form grid. Menus open above when needed, stay within the viewport and scroll when necessary. Existing responsive form stacking remains. Collapsed section stays below 190px. Computed menu icon contrast and option layout are checked. |
| Topology wiring | Existing browser assertions continue verifying Overview summaries, Platform headings/cards, category filters, Connectivity category tint, Network list/detail/nodes and membership styling. Registry, graph semantics and data contracts are unchanged. |

## N–Q: Executed validation

Commands run from `apps/web` unless stated otherwise.

| Check | Command and result |
| --- | --- |
| Focused frontend | `node --test tests/presentation.test.mjs tests/infrastructure-topology.test.mjs`: 11 passed. |
| Full frontend | `npm test`: 143 passed. |
| Production build | `npm run build`: passed. |
| Production browser | `node scripts/check-infrastructure-topology-browser.mjs`: **6 scenarios passed**, light/dark at 1440, 1100 and 800px. Includes Reference Data/Asset Category and Network form checks; no separate Reference Data browser script exists. |
| API regression | From `apps/api`, `.venv/bin/pytest -q tests/test_presentation.py tests/test_presentation_postgres.py tests/test_infrastructure_topology.py tests/test_infrastructure_topology_postgres.py`: 26 passed, no skips, with `ATLAS_TEST_DATABASE_URL` pointing to the disposable database. Includes strict invalid icon/accent rejection, registry parity, defaults, partial edits, real persistence, scope isolation and topology regressions. Existing deprecation warnings remain. |
| Browser script syntax | `node --check apps/web/scripts/check-infrastructure-topology-browser.mjs` from repository root: passed. |
| Whitespace | `git diff --check`: clean. |

The final browser run uses installed Chrome, Playwright under
`/tmp/atlas-topology-browser/node_modules/playwright/index.mjs`, and the production
frontend at `http://127.0.0.1:3112`. Screenshots are in
`/tmp/atlas-compact-browser-results`. Logs: `/tmp/atlas-compact-browser.log`,
`/tmp/atlas-compact-build.log`, `/tmp/atlas-compact-web-tests.log` and
`/tmp/atlas-compact-api.log`.

Initial API setup used the wrong local PostgreSQL role; rerunning with the
verified fixture role passed. The first browser attempt had a case-sensitive
assertion for the globally uppercased workspace labels; it was corrected.
Screenshot review caught an inherited dropdown-style override; picker-specific
selectors now preserve option flex layout, with a browser regression assertion.

## Compatibility, documentation and limits

No database, migration, API route/contract, authorization, customer/site scoping,
registry or traversal change was required. The disposable database was already
at `20260921_0020`. Browser saves use intercepted API fixtures; real persistence
and API rejection are separately covered by PostgreSQL tests. Live homelab
acceptance was not performed. No unresolved implementation or validation failures
remain. Temporary validation services were stopped afterward.

Administrator guides describe the compact interaction, and the architecture
text no longer describes always-visible native radio controls. The feature
ledger already correctly classifies shared category/Network presentation as
implemented; this polish does not change that classification.

## Material files

| File | Change |
| --- | --- |
| `apps/web/components/presentation-picker.js` | Shared compact menu controls, focus/keyboard handling, concise helper and preview. |
| `apps/web/app/presentation.css` | Compact controls, swatches, menus and selected/focus styling using existing tokens. |
| `apps/web/app/topology/page.js` | Remove the shared redundant context line. |
| `apps/web/app/globals.css` | Remove obsolete context-line styling. |
| `apps/web/scripts/check-infrastructure-topology-browser.mjs` | Update former radio interactions; add all-option, preview, save/reload, keyboard, theme, geometry and header checks. |
| `apps/web/tests/infrastructure-topology.test.mjs` | Shared-header regression check. |
| `docs/admin/asset-categories.md` | Explain compact choices, preview, saving and keyboard interaction. |
| `docs/admin/networks.md` | Document the same shared Network interaction. |
| `docs/architecture/infrastructure-topology.md` | Correct presentation-control accessibility description. |
| `docs/testing/infrastructure-topology-compact-pickers.md` | This completion/validation record. |

## Repository state

```text
 M apps/web/app/globals.css
 M apps/web/app/presentation.css
 M apps/web/app/topology/page.js
 M apps/web/components/presentation-picker.js
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M apps/web/tests/infrastructure-topology.test.mjs
 M docs/admin/asset-categories.md
 M docs/admin/networks.md
 M docs/architecture/infrastructure-topology.md
?? docs/testing/infrastructure-topology-compact-pickers.md
```
