# Topology and audit UI polish — acceptance record

## Branch and compatibility

The session started on `feature/ui-polish-topology-audit` at
`78783d1052cae47a9bb1355ec8a6a64d2e4b826c`, with a clean working tree.
The requested branch already existed and was retained. HEAD is unchanged;
no commits, pushes or merges were performed.

No migration was required. The existing single Alembic head is
`20260921_0023`. Connectivity's accepted hop range adds 3; existing URLs,
response contracts and domain semantics are preserved. PostgreSQL remains the
source of truth. Authorization and customer/site scoping are unchanged.

## Seven changes

1. **Topology inspectors:** Platform and Network/VLAN use the same Asset
   Inspector and graph-workspace styling as Connectivity. The shared
   `DetailsPanelToggle` is also used by Knowledge Graph. Selection persists
   while hidden, including changes made while hidden. Open Asset remains a
   native link. No bottom-page detail expansion remains.
2. **Overview:** the cap is 12, retaining deterministic name/ID ordering,
   existing wrapping, Asset links and category-filtered +N navigation. Counts
   continue to derive exclusively from the authorized projection.
3. **Platform:** minimum card footprint and stretched rows align parent cards.
   Four direct children appear in two columns, with +N more local expansion.
   Existing View platform controls support successive hierarchy exploration;
   card selection and drill controls remain separate. Canonical platform links
   supply the hierarchy; vendor/type names have no special behavior.
4. **Network/VLAN:** Name, Interface, IP address, MAC and Recorded status toggle
   ascending/descending with aria-sort and visible arrows. Address groups are
   parsed numerically, including compressed and IPv4-mapped IPv6. Equal values
   use Asset name, Asset ID and interface ID as deterministic secondary keys.
5. **Connectivity:** API/service accept depth 3. Only expanded UI offers it;
   closing returns 3 to 2 and preserves 1/2. Existing traversal, authorization,
   relationship-class filters, disclosure, 100-node and 500-edge limits and
   truthful truncation remain intact. Connectivity's eight-child canvas preview
   is intentionally unchanged; the four-child cap applies to Platform cards.
6. **Knowledge Graph:** the existing modal shell is retained. Expanded entry,
   inspector hide/show and measured viewport size changes recompute Fit using
   width and height. Selection is retained. Manual zoom/pan does not itself
   trigger Fit. Existing depth, filters, focus and inspector actions remain.
7. **Audit Log:** boxed +/− buttons disclose bounded full-width panels directly
   below their records, with multiple records independently open. Context and
   field differences render as labelled content. Both from/to and before/after
   shapes work, including nested snapshot fields and additions/removals.
   Unchanged nested values are omitted. Missing values are not invented.
   Existing backend redaction remains; the renderer also recursively suppresses
   sensitive keys. No audit collection or persistence fields changed.

Some existing events record only changed field names. Their panel explicitly
states that before/after values were not recorded; historical values cannot be
reconstructed from that metadata.

## Validation

Commands run from their respective application directories:

- `npm test`: 182 passed, no failures/skips.
- `npm run build`: passed production build.
- `.venv/bin/pytest -q tests/test_infrastructure_topology.py tests/test_infrastructure_topology_postgres.py tests/test_topology_layers.py tests/test_topology_layers_postgres.py tests/test_administration.py tests/test_auth.py`:
  104 passed, no skips, using a newly initialized and migrated disposable local
  PostgreSQL database. Existing dependency deprecation warnings remain.
- `.venv/bin/alembic heads`: `20260921_0023 (head)`.
- `git diff --check`: clean.
- `node apps/web/scripts/check-topology-audit-polish-browser.mjs`: all seven
  areas passed against the production Next.js server, with isolated HTTP
  fixtures and the real Python connectivity traversal. Covers 0/2/4/18-child
  parents, nested drilling, hidden selection, preview links, numeric sorting,
  both sort directions, fullscreen depth fallback, inspector resizing, manual
  zoom preservation, viewport refit and multiple audit records.
- `node apps/web/scripts/check-infrastructure-topology-browser.mjs`: all six
  existing topology/picker scenarios passed in light/dark at 1440, 1100 and
  800 pixels, including keyboard, selection, filters, disclosure and refocus.
- `node apps/web/scripts/check-expanded-graph-browser.mjs`: all eight existing
  light/dark and desktop/narrow viewport scenarios passed.

Browser scripts used `ATLAS_PLAYWRIGHT_MODULE` pointing to the existing local
Playwright installation, `ATLAS_CHROME_PATH` pointing to installed Chrome,
`ATLAS_BROWSER_BASE_URL=http://127.0.0.1:3118`, and separate output directories.
No live Atlas records were modified. Browser fixtures verify presentation;
PostgreSQL tests independently verify backend access and traversal behavior.

## Screenshots

Ten representative captures were visually inspected, not just DOM-asserted.
They are in `/tmp/atlas-topology-audit-polish/`:

| Capture | Evidence |
| --- | --- |
| `01-overview-12-plus-5.png` | Twelve icons and +5, wrapping |
| `02-platform-inspector-four-children.png` | Right inspector and aligned parent cards |
| `03-network-inspector-sorted-ips.png` | Network membership and right inspector |
| `04-connectivity-three-hops.png` | Expanded three-hop controls and graph |
| `05-knowledge-visible.png` | Expanded fitted three-lane graph and inspector |
| `06-knowledge-hidden.png` | Canvas uses released inspector width |
| `07-audit-collapsed.png` | Compact boxed disclosures |
| `08-audit-expanded-diffs.png` | Multiple inline before/after investigations |
| `09-platform-child-preview.png` | Four direct child tiles and +14 |
| `10-network-ip-sort.png` | Numeric .2, .9, .20, .100 ordering |

## Material files

- `apps/api/app/routes/topology.py` and
  `apps/api/app/services/infrastructure_topology.py`: additive depth-3 validation.
- `apps/api/tests/test_infrastructure_topology.py` and
  `apps/api/tests/test_infrastructure_topology_postgres.py`: traversal/scope/limit regressions.
- `apps/web/app/topology/page.js`, `lib/infrastructure-topology.mjs`,
  `lib/network-sort.mjs`: inspectors, previews, drilling, sorting and hop controls.
- `apps/web/app/knowledge-graph/page.js`, `components/service-landscape.js`,
  `components/details-panel-toggle.js`: shared panel controls and viewport Fit.
- `apps/web/app/admin/audit/page.js`, `components/audit-investigation.js`,
  `lib/audit-details.mjs`: inline audit investigation and safe structured differences.
- `apps/web/app/globals.css`: card alignment, inspector width and bounded audit layout.
- `apps/web/tests/infrastructure-topology.test.mjs`,
  `tests/topology-audit-polish.test.mjs`: preview/address/diff regressions.
- `apps/web/scripts/check-topology-audit-polish-browser.mjs` and
  `scripts/check-infrastructure-topology-browser.mjs`: new acceptance and updated
  existing expectations for requested inspector/preview behavior.
- `docs/admin/infrastructure-topology.md`, `docs/admin/knowledge-graph.md`,
  `docs/architecture/infrastructure-topology.md`, `docs/product/feature-ledger.md`
  and this record: current behavior and validation evidence.

## Final repository state

`git status --short` (all changes belong to this task):

```text
 M apps/api/app/routes/topology.py
 M apps/api/app/services/infrastructure_topology.py
 M apps/api/tests/test_infrastructure_topology.py
 M apps/api/tests/test_infrastructure_topology_postgres.py
 M apps/web/app/admin/audit/page.js
 M apps/web/app/globals.css
 M apps/web/app/knowledge-graph/page.js
 M apps/web/app/topology/page.js
 M apps/web/components/service-landscape.js
 M apps/web/lib/infrastructure-topology.mjs
 M apps/web/scripts/check-infrastructure-topology-browser.mjs
 M apps/web/tests/infrastructure-topology.test.mjs
 M docs/admin/infrastructure-topology.md
 M docs/admin/knowledge-graph.md
 M docs/architecture/infrastructure-topology.md
 M docs/product/feature-ledger.md
?? apps/web/components/audit-investigation.js
?? apps/web/components/details-panel-toggle.js
?? apps/web/lib/audit-details.mjs
?? apps/web/lib/network-sort.mjs
?? apps/web/scripts/check-topology-audit-polish-browser.mjs
?? apps/web/tests/topology-audit-polish.test.mjs
?? docs/testing/topology-audit-ui-polish.md
```
