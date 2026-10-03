# Atlas Impact — UI System Review and Design Cleanup Specification

**Status:** Historical audit and rationale. Future UI work follows [the canonical UI architecture guide](../../architecture/ui-architecture.md); this review is not an implementation-status record.

**Review date:** 28 September 2026  
**Scope:** `apps/web` in the supplied Atlas Impact source tree  
**Purpose:** Establish a single, polished and maintainable UI language across Atlas Impact before a dedicated design-cleanup release.  
**Revised direction:** Preserve Atlas's richer visual identity — especially the Asset experience — while standardising typography, interaction behaviour and reusable frontend architecture. Consistency means shared standards and code assets, not visual sameness.

---

## 1. Executive summary

Atlas Impact already has a strong visual foundation. The neutral palette, restrained use of colour, application shell, customer/site context selector, dark mode, accessibility work in the graph/topology views, configurable accent theme, and newer Services/Business Functions catalogue are all moving in the right direction.

The main issue is not that the UI is unattractive. It is that **several generations of UI patterns now coexist**:

1. the original form/table CRUD language;
2. bespoke Assets list/detail patterns;
3. the newer Services/Business Functions catalogue and detail language;
4. the newer Operations/graph/topology card language;
5. separate icon/identity systems for Assets, entity types, presentation identity and navigation.

Each is internally reasonable, but together they make Atlas feel assembled feature-by-feature rather than governed by a mature product design system. This is the principal source of the remaining “AI-built” feel: not decorative styling, but **small inconsistencies in hierarchy, component behaviour, spacing, naming, status semantics and identity treatment**.

The design-cleanup release should therefore **not begin by visually redesigning every page**. It should first establish a compact Atlas UI system and migrate pages onto it. This is as much a frontend-architecture refactor as a visual cleanup. The intended outcome is that new screens naturally inherit Atlas standards because they are built from reusable primitives and domain components, not because a developer or Codex prompt manually copies styling from another page.

The recommended end state is:

- one loaded application font and a defined type scale;
- one page-heading system;
- one entity identity contract for Asset, Service, Business Function and Network;
- one status-semantic registry;
- one shared search/filter interaction model;
- one reusable entity-collection framework that supports different visual treatments rather than forcing identical rows;
- one data-table system for administrative/reference records;
- one family of surfaces/sections rather than many subtly different cards;
- one button and icon-button system;
- one set of utility icons rather than Unicode controls;
- explicit copy/capitalisation rules;
- tenant-aware component boundaries that do not assume a permanently single-tenant product;
- consistent desktop, tablet, mobile, keyboard, dark-mode and empty/error/loading behaviour.

If those changes are made systematically, Atlas can look intentionally designed without becoming decorative or fashionable. The target should be **quiet, information-dense operational software with a distinctive Atlas identity**: modern, restrained, fast to scan, visually richer than a generic SaaS admin tool, and consistent because the implementation itself is consistent.

---

## 2. Audit method and scope

This is a **source-level UI system audit** of the supplied application. I reviewed the web application routes, shared components and styling rather than judging isolated screenshots. The review covers:

- typography and heading hierarchy;
- page headers and information hierarchy;
- spacing and density;
- cards, panels and other surfaces;
- list/catalogue patterns;
- tables and administrative CRUD screens;
- filters, forms and controls;
- entity identity and iconography;
- status and semantic colour;
- navigation and shell consistency;
- responsive behaviour;
- keyboard/focus accessibility;
- user-facing language and product polish;
- implementation architecture and design-system maintainability.

The supplied source contains **43 route pages** and approximately **45 top-level shared components** in the web application. The principal global stylesheet is approximately 1,442 lines, plus the presentation-identity stylesheet.

This was not a live visual-regression run because the supplied repository did not include installed web dependencies. The findings below therefore identify structural and implementation inconsistencies directly from the source. A final visual acceptance pass at defined viewport sizes should be part of the cleanup release.

---

# 3. What should be preserved

A cleanup should consolidate Atlas, not erase the work that is already good.

## 3.1 Colour foundation

The global semantic palette is restrained and appropriate for an operational product. The application distinguishes background, surface, border, muted text, accent, success, warning, danger and informational colours at the token level (`apps/web/app/globals.css:3–33`).

The custom accent implementation is particularly worth retaining. Atlas derives hover, soft, border and focus treatments from the selected accent and performs contrast-aware calculation rather than simply tinting arbitrary colours. This is a mature approach and should remain the basis of workspace theming.

## 3.2 Presentation identity separation

`presentation.css` deliberately separates presentation/identity colour from operational semantic colour. That is the correct conceptual model:

- **identity colour** answers “what is this?”;
- **status colour** answers “what state is it in?”.

Those two meanings should never be combined. The current Asset Category and Network presentation picker is therefore a good pattern to extend.

## 3.3 Asset visual identity and newer catalogue interaction patterns

Two different parts of Atlas currently contain the strongest ideas for first-class entity browsing, and the cleanup should combine them rather than choosing one over the other.

The **Asset page has the stronger visual identity**: real or recognisable icons, stronger entity recognition and a more distinctive Atlas feel. The **Services/Business Functions catalogue has the stronger interaction model**: linked rows, concise hierarchy, automatic search, quick and advanced filters, responsive collapse and better keyboard treatment.

The target should therefore be an **Atlas Entity Collection** pattern that takes the Asset page as the aesthetic baseline and the newer catalogues as the information-architecture and interaction baseline. Reuse should standardise behaviour, typography, spacing, search, filters, focus, responsive rules and entity identity contracts without forcing Asset, Service and Business Function rows to be visually identical.

## 3.4 Service/Business Function detail shell

The shared entity-detail work is another good foundation. A consistent identity/header/section model is more coherent than the older Asset detail page, and it should become the general entity-detail shell.

## 3.5 Asset icon fallback architecture

The Asset icon implementation has useful product logic. It can resolve a cached Asset icon, fall back to an Asset Type default, and finally render a safe generic icon (`components/asset-icon.js:20–26`). That behaviour should be retained. The cleanup is about placing that logic inside the same **visual identity contract** used by the other entity types, not replacing it with generic symbols.

## 3.6 Accessibility groundwork

There is already meaningful accessibility work: focus styles on several navigation/control families, `aria` status labels, responsive catalogue layouts, graph/topology keyboard handling and `prefers-reduced-motion` support. This means accessibility can be normalised rather than introduced from scratch.

---

# 4. Principal findings

## 4.1 Atlas currently has multiple overlapping design systems

This is the most important finding.

A user moving between pages can encounter:

- classic bordered form cards and raw tables;
- bespoke Asset filters and Asset detail cards;
- catalogue rows for Services/Business Functions;
- Operations cards with different heading sizes and radii;
- specialised reconciliation/knowledge-gap cards;
- graph/topology inspectors and toolbars.

Specialised experiences are appropriate where the task genuinely differs. The problem is that common concerns — headings, identity, status, section structure, filters and actions — are also being reimplemented inside those experiences.

### Recommendation

Introduce a small set of **product-level primitives** and require specialised pages to compose them rather than restyle them:

- `PageHeader`
- `EntityIdentity`
- `EntityDetailHeader`
- `Section`
- `Surface`
- `SearchFilterBar`
- `EntityCollection` / `EntityCollectionRow`
- `DataTable`
- `StatusIndicator`
- `Badge/Tag`
- `Button`
- `IconButton`
- `EmptyState`
- `InlineNotice`

Then build small **domain components** on top of those primitives, for example `AssetIdentity`, `ServiceIdentity`, `BusinessFunctionIdentity` and `NetworkIdentity`. These components should share the common visual contract while retaining genuine domain-specific behaviour such as Asset vendor/workload imagery or Service Type presentation identity.

The objective is not to create a huge component library or one giant generic `EntityPage` with dozens of configuration props. Prefer **small composable primitives with clear responsibilities**. Shared behaviour belongs in the primitive; genuine domain differences remain in domain components. The common 80% should be difficult to implement inconsistently without making every page look the same.

---

# 5. Typography

## 5.1 The declared font is not actually loaded

The root style declares:

`Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`

at `apps/web/app/globals.css:33`.

However, the application layout does not load Inter using `next/font` or another font source. On machines without Inter installed, Atlas therefore uses the operating-system fallback. This means typography can differ noticeably between macOS/iOS, Windows and Linux.

### Recommendation

Choose one of two deliberate strategies:

**Preferred:** bundle/load Inter through `next/font` and make the result deterministic. This is appropriate for a self-hosted application because it avoids third-party font requests and produces the same metrics everywhere.

**Alternative:** deliberately use system UI and remove `Inter` from the declaration. This is extremely robust but less visually consistent between platforms.

Do not continue with an implied Inter design that silently changes to another font.

## 5.2 Too many type sizes are in active CSS

The stylesheet contains more than twenty distinct `font-size` values, including 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27, 28, 30 and 42px variants.

Not all are wrong individually, but the accumulated effect is that hierarchy is decided component-by-component rather than by a type system.

## 5.3 Font weights are similarly irregular

Values such as `550`, `650` and `750` occur throughout the CSS. Those are valid for a variable font, but if the requested font is not actually loaded, fallback fonts may not expose those exact weights and the browser can synthesise them.

### Recommended type scale

Use a deliberately small scale and standard weights:

| Role | Size | Weight | Line height | Notes |
|---|---:|---:|---:|---|
| Page H1 | 28px | 700 | 1.15 | One value across standard pages |
| Section H2 | 16px | 600 | 1.35 | Primary section title |
| Subsection H3 | 14px | 600 | 1.4 | Nested group title |
| Entity/list title | 15px | 600 | 1.35 | Catalogue/list identity |
| Body | 14px | 400 | 1.5 | Normal reading text |
| Compact body/table | 13px | 400 | 1.45 | Dense operational UI |
| Label | 12px | 600 | 1.35 | Form/meta label |
| Meta | 11–12px | 500 | 1.35 | Secondary metadata |

Use 400/500/600/700 by default. Only introduce a non-standard weight when the actual font guarantees it and there is a visible reason.

## 5.4 Page H1 is inconsistent today

The general page H1 is 30px (`globals.css:290`). Pages wrapped in `.operations-page` override it to 27px (`globals.css:966–968`). That means Dashboard, Knowledge Graph, Topology and the newer entity-detail pages have a different H1 size from many inventory/admin pages.

The difference is subtle enough to look accidental rather than intentional.

### Recommendation

Use one H1 size for ordinary product pages. If graph/canvas pages require a compact header, express that through a named `compact` PageHeader variant, not through a broad `.operations-page` cascade.

## 5.5 Section heading hierarchy varies too much

Examples include:

- form card H2: 17px (`globals.css:361`);
- Operations card H2: 16px (`globals.css:970`);
- reconciliation H2: 20px;
- profile card H2: 22px;
- knowledge-gap H2: 16px while a nested missing-knowledge H3 is 17px (`globals.css:728–730`).

The Knowledge Gaps example is a concrete hierarchy error: a nested H3 can display larger than its parent H2.

### Recommendation

Normalize headings by semantic depth, not by feature. Component styling must not invert semantic hierarchy.

## 5.6 Catalogue title and description are too close

The Services/Business Functions catalogue currently renders:

- name at 15px/650;
- description at 14px/400;
- context at 12px.

(`globals.css:1429–1431`)

This is functional, but the 1px difference between title and description makes longer descriptions compete with the entity name. This matches the visual concern already observed on the list pages.

### Recommendation

Use:

- entity name: **15px / 600**;
- description: **13px / 400 / muted or slightly softened text**;
- context: **11–12px / 500 / muted**.

This preserves density while making the eye land on the identity first.

---

# 6. Page headings and page structure

## 6.1 `PageHeader` is too limited

The current component (`components/page-header.js:1–9`) supports only:

- eyebrow;
- title;
- description.

Actions are therefore implemented beside it using a separate `.page-heading-row`, while entity pages separately add breadcrumbs, marks and metadata.

It also always renders the description paragraph, even when `description` is empty or undefined.

### Recommendation: make `PageHeader` the complete page-heading primitive

It should support:

- optional breadcrumb/context;
- optional entity identity/icon;
- title;
- optional description;
- actions;
- optional compact metadata row;
- `standard | compact | canvas` layout variant.

It should own heading spacing and mobile stacking itself. Pages should not create their own header flex layout.

## 6.2 Eyebrow use is inconsistent and contributes to template feel

Examples include `Knowledge`, `Inventory`, `Operations`, `Connectivity`, `Organisation`, `Locations`, `Reference Data` and `System`, while Dashboard and Knowledge Graph can omit it entirely.

Decorative uppercase category labels on nearly every page are a common dashboard-template convention. They are most useful when they provide real navigation context; otherwise they add visual ceremony without information.

### Recommendation

Use context only when it helps orientation:

- **primary application pages:** H1 + short description + actions; no eyebrow by default;
- **detail pages:** breadcrumb + identity + H1; no “Asset detail” eyebrow;
- **create/edit pages:** breadcrumb + H1;
- **administration:** breadcrumb or stable Administration context, not a decorative category on every screen.

This will make Atlas feel more like purposeful product software and less like a generated dashboard template.

## 6.3 Descriptions should be short and task-oriented

Page descriptions are generally good, but a design cleanup should apply one rule: explain **what the user can do here**, not restate the page title or explain the product concept at length.

Target one line on a normal desktop wherever practical.

---

# 7. Spacing, radii and surface system

## 7.1 Radius values have proliferated

The CSS contains many radii: 2, 4, 5, 6, 7, 8, 9, 10, 12, 14, 20px, `.75rem`, 50% and pill radii.

Again, each value may be defensible in isolation, but they create a subtle “different component, different designer” effect.

### Recommended radius tokens

- `--radius-control: 7px`
- `--radius-surface: 10px`
- `--radius-overlay: 12px`
- `--radius-pill: 999px`

Allow circles where semantically required.

Do not use a different radius simply to make a component feel special.

## 7.2 Surface/card patterns should be reduced

Current patterns include `.form-card`, `.table-card`, `.detail-card`, `.knowledge-card`, `.ops-card`, `.reconciliation-card`, filter cards, legacy profile/admin/summary cards and feature-specific cards.

### Recommendation

Define three levels:

1. **Section** — normally no decorative background; uses spacing/dividers.
2. **Surface** — bordered surface for a meaningful grouped unit.
3. **Overlay** — dialog/dropdown/floating inspector with shadow/elevation.

A page should not become a stack of white cards simply because each subsection needs a heading. Cards should communicate grouping or interaction.

This is a major way to remove an “AI dashboard” appearance: fewer generic cards, stronger information structure.

## 7.3 Recommended spacing scale

Use a small base scale everywhere:

`4, 8, 12, 16, 20, 24, 32px`

Suggested rules:

- control internal gap: 8px;
- list-row vertical padding: 14–16px;
- surface padding: 16–20px;
- section gap: 16–20px;
- major page section gap: 24–32px;
- page horizontal padding: responsive token rather than repeated values.

---

# 8. First-class entity collections: Assets, Services and Business Functions

This is one of the most visible cross-application inconsistencies, but the solution should **not** be to flatten all three entity families into the same row design.

## 8.1 Assets provide the stronger visual baseline

The Asset page has richer visual identity through real/cached icons, Asset Type fallbacks and stronger recognition of infrastructure/workload entities. That richness is valuable and should be preserved. It gives Atlas character and makes scanning faster than a text-heavy generic catalogue.

The weaknesses of the current Asset page are primarily structural and behavioural: bespoke search/filter behaviour, older typography, table-oriented density, inconsistent action placement and a separate interaction grammar.

## 8.2 Services and Business Functions provide the stronger interaction baseline

The newer shared catalogue provides:

- linked full-row interaction;
- concise identity, description and context hierarchy;
- automatic/debounced search;
- quick and advanced filters;
- responsive collapse;
- good keyboard focus treatment.

Those interaction patterns should be reused across first-class entity collections.

## 8.3 Target: one Entity Collection framework, multiple domain presentations

Create a shared `EntityCollection` / `EntityCollectionRow` framework that owns:

- list structure and spacing;
- search/filter integration;
- loading/empty/error states;
- keyboard and focus behaviour;
- responsive collapse;
- row link/action conventions;
- common typography tokens;
- metadata slots;
- optional operational/status slots.

Each entity family then composes the row differently.

### Asset row

Preserve the richer Asset identity:

- vendor/workload/Asset Type icon;
- Asset name;
- Asset Type and hostname/IP/site context;
- recorded status;
- completeness or attention signal where useful.

The icon should remain visually important. Do not reduce Assets to a generic glyph merely to achieve consistency.

### Service row

Use Service Type identity with an icon + restrained presentation colour, Service name, description, criticality/dependency context and operational state. The visual weight should be similar to Assets even though the internal identity source differs.

### Business Function row

Use an automatically assigned function identity, name, description, criticality/ownership/service context and operational/knowledge signals where relevant. Again, the shared framework should provide consistency without making the row indistinguishable from a Service or Asset.

## 8.4 Search/filter behaviour should be shared even when presentation differs

Build one reusable `SearchFilterBar` rather than separately redesigning search for Assets, Services, Business Functions, Networks and future tenant-aware views. It should own:

- collapsed/expanded presentation;
- text search styling and debounce behaviour;
- active-filter count;
- Clear/reset behaviour;
- responsive layout;
- keyboard behaviour;
- URL/query-state conventions where useful;
- filter chips/summary;
- common spacing and typography.

Pages should supply their filter definitions and query behaviour rather than reimplementing the interaction shell.

This gives Atlas a consistent standard without sacrificing visual identity.

# 9. Tables

## 9.1 Tables are still appropriate — but for data records, not every entity list

Atlas should keep tables for:

- reference data;
- administration;
- audit/activity records;
- discovery records;
- dense relationship/interface data;
- other datasets where cross-row column comparison is the task.

The entity catalogue is preferable when the task is browsing named domain entities.

## 9.2 The table implementation is fragmented

There is a `DataTable` component, but most real pages and `CrudScreen` render raw tables directly. The existing DataTable also contains sample-data semantics, so it is not currently the canonical application table primitive.

### Recommendation

Create one production `DataTable` primitive supporting:

- column definitions;
- optional sorting;
- row link/action behaviour;
- compact and standard density;
- loading skeleton;
- empty state;
- error state;
- horizontal overflow;
- accessible column headers and sort state;
- optional bulk selection only where actually needed.

Then move CRUD/admin tables and specialised tables to the primitive progressively.

## 9.3 Current table typography is broadly good

The existing direction — approximately 11px uppercase headers and 13px cells — is appropriate for dense operational data. The cleanup should retain that density but standardise it as a tokenized table style.

### Recommended table rules

- header: 11px/600; muted; uppercase only for short column labels;
- cell: 13px/400;
- strong identity cell: 13px/600;
- standard row height: approximately 44–48px;
- row hover only when the row is interactive;
- avoid action columns containing multiple text links where a single row-click and overflow menu would be clearer.

---

# 10. Entity identity and iconography

This is the second major system-level cleanup area after page/list consistency.

## 10.1 Four icon/identity systems currently coexist

### A. Asset icons

`AssetIcon` uses real/cached images and safe fallbacks. Good functional system, but visually separate from generic entities.

### B. Generic entity marks

`EntityMark` hardcodes:

- cube for Asset;
- globe for Service;
- people for Business Function.

(`components/operations-primitives.js:16–20`)

These marks provide category recognition but do not reflect the entity’s actual type/purpose.

### C. Presentation Identity

Asset Categories and Networks use a bounded icon/accent registry through `PresentationIcon`, `PresentationIdentity` and `PresentationPicker`. This is the strongest reusable identity architecture.

### D. Navigation icons

The sidebar has a consistent line-icon set of its own. That is appropriate for navigation, but it also contains many symbols that can be reused inside the bounded presentation registry.

## 10.2 Service Type currently has only a free-text icon key

The Service Type administration page exposes `icon_key` as a plain text field labelled “Icon key” with an optional display hint. It does not use the bounded picker and has no matching accent selector.

This is both a UI and data-quality inconsistency: users can create unknown keys and there is no visual preview.

## 10.3 Business Functions have no equivalent identity configuration

Business Functions currently fall back to a generic category mark. This will become increasingly visible in catalogue, graph, topology and dashboard surfaces as the product matures.

### Recommended target: one `EntityIdentity` contract

Build a shared entity-identity abstraction that can render any first-class Atlas entity while allowing each entity family to resolve its identity differently.

#### Assets

Resolution order:

1. cached/discovered Asset icon;
2. Asset Type default icon;
3. neutral generic Asset fallback.

Keep this behaviour.

#### Services

A Service should inherit its presentation identity from **Service Type** by default.

Change Service Type configuration from a free-text key to the same bounded `PresentationPicker` model already used elsewhere. Add `accent_key` alongside `icon_key`.

This provides a stable visual vocabulary without forcing users to choose an icon for every Service.

#### Business Functions

Business Functions do not currently have a type taxonomy, so store presentation identity directly on the Business Function:

- `icon_key`;
- `accent_key`.

At creation, **silently assign a deterministic sensible default** and allow the user to alter it through the same picker. Avoid random assignment: the same input/default logic should yield predictable product behaviour.

#### Networks

Retain the current Presentation Identity approach.

## 10.4 Standardise identity sizes

The visual container, alignment and spacing should be consistent even if the internal icon source differs.

Recommended sizes:

- **24–28px:** dense relationship/graph/table contexts;
- **32px:** compact entity row;
- **38–40px:** primary catalogue row;
- **48–56px:** detail-page identity.

Use the same optical box/radius/alignment contract for all entities.

## 10.5 Identity colour must never become status colour

A purple Service remains purple whether it is operational or unavailable. Its status is represented by the status indicator beside it, not by recolouring its identity.

This distinction should be explicit in component APIs and documented in the design system.

## 10.6 Replace Unicode UI controls with a shared utility icon set

Atlas currently uses visible characters such as:

- `×` for close;
- `›` and `⌄` for chevrons;
- `↗` for external/open;
- `✓` for confirmation;
- `↑/↓` for sorting.

Semantic relationship arrows such as `→` or `↔` are acceptable because they describe data. UI controls should instead use consistent SVG utility icons so stroke, alignment, hit area and accessibility are controlled.

Add common icons to the shared icon component:

- close;
- chevron-right;
- chevron-down;
- external-link;
- check;
- sort-up;
- sort-down;
- search;
- filter;
- more;
- edit;
- delete where appropriate.

---

# 11. Status, badges and semantic colour

## 11.1 Status is represented in multiple ways

Atlas has:

- `RecordedStatus` dot;
- `StatusBadge` pill;
- raw textual statuses;
- feature-specific status CSS.

That is reasonable if each representation has a defined semantic purpose. Currently the mapping itself can also differ.

## 11.2 Concrete inconsistency: maintenance

The catalogue maps maintenance to warning (`globals.css:1435–1436`).

The entity-detail override maps maintenance to informational blue (`globals.css:1223–1224`).

The same recorded state therefore changes semantic colour by screen.

### Recommendation: central status registry

Create one `statusRegistry` defining, for each application state:

- canonical key;
- human label;
- semantic tone;
- optional icon;
- applicability/domain.

Then use a single `StatusIndicator` component with display variants.

Suggested conventions:

- **operational state:** dot + text;
- **workflow/review state:** compact badge/tag;
- **lifecycle state:** neutral text/tag unless attention is required;
- **severity:** semantic badge;
- **completeness:** percentage/progress treatment, not a generic status pill.

Avoid converting every metadata field into a coloured pill. Excess badges create visual noise and are another common generated-dashboard characteristic.

---

# 12. Detail pages

## 12.1 Service and Business Function details are converging

The newer shared entity-detail components establish a clearer common shell.

## 12.2 Asset detail remains its own design system

Asset detail uses its own heading treatment, `AssetIcon`, older detail/form/table/knowledge cards and feature-specific layout rather than the newer entity-detail primitives.

### Recommendation

Migrate Asset detail onto the same **structural** detail shell used by the newer entity pages, but preserve the richer Asset identity and entity-specific content.

A shared detail skeleton should be:

1. breadcrumb/context;
2. entity identity + H1 + concise description;
3. metadata/status/completeness strip;
4. primary actions;
5. consistent section primitives below.

The shell should standardise hierarchy, spacing, actions, metadata, responsive behaviour and accessibility. It should **not** dictate identical content cards or identical identity treatment. Asset, Service and Business Function detail pages should remain recognisably different domain views built from the same architectural grammar.

This will make navigating Asset → Service → Business Function feel coherent without flattening Atlas into one generic entity template.

---

# 13. Buttons, controls and interaction consistency

## 13.1 Base button styling is usable but incomplete as a system

The global `.button` is 13px/650 with 9×14px padding and an 8px radius (`globals.css:296–304`). It does not define a standard minimum height, and generic focus-visible treatment is not universal.

### Recommendation

Define explicit variants and sizes:

- Primary
- Secondary
- Ghost
- Danger
- Icon-only
- Text/link action

Default desktop control height: **36px**.  
Touch-oriented layouts: **40–44px** where practical.

Do not let each feature invent its own clickable dimensions.

## 13.2 Icon buttons need a real primitive

The current `.icon-button` only sets transparent background, no border, muted colour, cursor and a 23px font size (`globals.css:362`). It has no defined square hit target or universal focus ring.

Some icon-only controls have accessible labels; at least one Business Function close control uses `×` without an explicit `aria-label`.

### Recommendation

Create `IconButton` with:

- 36×36 standard target;
- centered SVG icon;
- hover surface;
- focus-visible ring;
- disabled state;
- required accessible label;
- optional tooltip;
- danger variant.

Prevent unlabeled icon buttons at component/API level if possible.

## 13.3 Universal focus treatment is needed

Some parts of Atlas have excellent focus treatment. `.operations-page` explicitly provides a 3px focus outline for buttons/links (`globals.css:1096`), and navigation/fields also have local focus rules.

The inconsistency is that controls outside those scopes do not all inherit the same keyboard affordance.

### Recommendation

Add a global base rule such as:

`:where(a, button, input, select, textarea, summary):focus-visible`

and only override it for highly specialised canvas interactions.

Keyboard focus should not become stronger or weaker depending on which feature team/style block created the page.

---

# 14. Forms and filters

## 14.1 Form fields are relatively consistent

The global field pattern at `globals.css:363–379` is a sound base. It should become tokenized rather than repeatedly overridden.

## 14.2 Filter behaviour is not consistent

Services/Business Functions use debounced search; Assets currently require an Apply action. Other operational pages use their own filter-toolbar structures.

### Recommendation

Standardise by interaction type and implement the behaviour once in `SearchFilterBar`:

- text search: debounced automatically;
- checkboxes/toggles/simple selects: apply immediately unless an expensive query makes batching necessary;
- complex multi-filter query: optionally use Apply, but then use that pattern consistently;
- Clear filters always appears in the same position and only when filters are active;
- filter state should support URL/query persistence where it benefits navigation and deep-linking.

Pages should configure available filters rather than reimplementing search/filter layout and state handling. Users should not have to learn whether Enter, Apply, or pausing will update results on each page.

## 14.3 The presentation picker should be the model for bounded visual settings

Asset Categories and Networks already show a proper visual picker/preview. Reuse that for Service Types and Business Functions instead of free-text keys.

---

# 15. Navigation and application shell

## 15.1 Navigation is structurally strong

The 244px sidebar, grouped navigation, active state and top context bar provide a stable application frame. The line-icon system is visually consistent.

## 15.2 The sidebar footer exposes development scaffolding

`components/app-shell.js:42` renders:

`Atlas Impact`  
`Local development`

This is appropriate during development but should not remain as ordinary production UI. It immediately makes a polished application feel like a developer build.

### Recommendation

Use one of:

- no footer text;
- application version/build only, e.g. `v0.x.x`;
- environment label only when the environment is actually non-production, rendered intentionally as an environment badge.

Never hardcode “Local development” into the standard shell.

## 15.3 Tablet navigation deserves final visual QA

At the existing tablet breakpoint the fixed sidebar becomes a horizontal/static navigation treatment. This is a reasonable responsive solution, but the number of grouped destinations means it needs deliberate viewport testing rather than being assumed to work because the CSS wraps/scrolls.

If it feels crowded at 768–900px, prefer a compact drawer/navigation disclosure rather than shrinking text or controls.

---

# 16. Multi-tenant and MSP readiness

Atlas is currently being designed primarily for a single operating context, but the UI architecture should not assume that this will always be true. A future MSP operator may move frequently between customers while viewing the same entity types and operational workflows.

## 16.1 Keep tenant context separate from entity identity

Do not use entity colour, status colour or Asset/Service identity to represent the selected tenant. These are different semantic layers:

- **tenant context** answers “which customer/organisation am I operating in?”;
- **entity identity** answers “what is this entity?”;
- **status/severity** answers “what state is it in?”.

A future tenant switcher/context control belongs in the application shell, for example a persistent organisation/customer context near the top-level navigation. Entity components beneath it should continue to use normal Atlas identities.

## 16.2 Components should be tenant-aware without looking like an MSP console today

Reusable components should avoid assumptions that IDs, cached entities, selection state or routes are globally unique across the whole installation. Where practical, component APIs and frontend state should be designed so tenant/workspace context can be introduced without a later visual rewrite.

Examples:

- route and cache keys should be able to incorporate tenant/workspace context;
- search/filter state should be scoped to the active tenant where applicable;
- entity identity components should accept context rather than reading singleton global assumptions;
- cross-tenant navigation should always make the active tenant explicit before a destructive or high-impact action.

The rule is: **design reusable code for multi-tenancy now, but do not clutter the current single-tenant experience with premature MSP UI.**

# 17. Responsive behaviour

Responsive work is already present and should be preserved.

Positive examples include:

- catalogue rows collapsing to one column below 640px;
- advanced filters reducing from three columns to two and then one;
- form grids stacking;
- Asset list toolbar eventually becoming one column;
- tables intentionally using horizontal overflow instead of crushing columns.

### Design-cleanup verification matrix

Every primary template should be checked at minimum at:

- **1440px** desktop;
- **1024px** compact desktop/tablet landscape;
- **768–900px** tablet/navigation transition;
- **390px** phone.

Test each in light and dark mode and with both default and custom accent colours.

Also test:

- long entity names;
- long descriptions;
- missing descriptions/icons;
- large status labels;
- empty data;
- loading data;
- permission/error states;
- tables wider than viewport;
- graph inspector open/closed.

---

# 18. Language, capitalisation and microcopy

Atlas currently mixes conventions such as:

- `Audit log` versus `System Settings`;
- `Knowledge Gaps`, `Knowledge Graph`, `Infrastructure Topology`;
- `My profile`;
- `Add Service`, `Add Business Function`, but `Add asset`/`Edit asset` in other locations.

The issue is not whether Title Case or sentence case is intrinsically correct. It is that the choice is inconsistent.

### Recommended product writing rule

Use **sentence case** for UI labels and actions unless a term is an intentional Atlas domain-model proper noun.

Create a tiny terminology dictionary deciding whether model terms are branded concepts or normal nouns. For example:

- Atlas Impact — proper product name;
- Service / service — choose one product-wide convention;
- Business Function / business function — choose one product-wide convention;
- Asset / asset — choose one product-wide convention;
- Knowledge Graph — if this is a named Atlas feature, keep as feature title, but use “knowledge graph” in explanatory prose.

Actions should consistently be sentence case: `Add service`, `Edit asset`, `Clear filters`, `View all`.

The cleanup should include copy review alongside CSS/component migration; inconsistent language is highly visible in an otherwise refined UI.

---

# 19. Production polish and “AI feel”

The request that Atlas should “not at all feel like AI” is best solved structurally rather than by adding more visual styling.

## 18.1 What tends to create the generated-product feeling in the current app

- every new feature gaining a bespoke card style;
- many near-identical but non-identical radii and font sizes;
- uppercase eyebrow labels used as decoration;
- card-on-card layouts when a simple section divider would work;
- excessive status pills;
- generic icons where meaningful identity is available;
- inconsistent interaction models between similar pages;
- scaffolding text visible to users;
- “sample data”, “local development”, and future-feature prose in production surfaces;
- pages with slightly different heading/body scales.

## 18.2 What will make Atlas feel authored and mature

- quiet, deliberate type hierarchy;
- fewer components, used more consistently;
- strong entity identity that persists between catalogue, detail, graph and topology;
- restrained semantic colour;
- meaningful white space rather than decorative card separation;
- predictable controls;
- concise domain-specific copy;
- excellent empty/loading/error states;
- attention to keyboard interaction and responsive edge cases;
- visual continuity across every path to the same entity.

The goal should not be “make every page look the same.” It should be “make every page obviously belong to the same product.”

---

# 20. User-facing development placeholders to remove or formalise

Several source areas expose implementation-stage language.

## 19.1 Integrations

The current Integrations path uses a mock/sample-page pattern and visibly communicates sample data. Before a polish release, it should either:

- become a real feature surface; or
- be hidden/feature-flagged until ready.

A product-quality navigation item should not open a mock application page.

## 19.2 System Settings

Some settings sections explain that future capabilities “will be added here” or “will be available here”, including backup/restore and update areas.

### Recommendation

Either:

- hide unavailable settings until they ship; or
- present a deliberately designed `Not available in this release` state only where knowing about the capability is genuinely useful.

Avoid roadmap prose inside operational settings screens.

## 19.3 Development environment footer

Remove or conditionally render `Local development` as described above.

---

# 21. CSS and implementation maintainability

## 20.1 The global stylesheet now contains historical layers

The main stylesheet combines shell, forms, tables, feature-specific pages, legacy dashboard styles, graph/topology styles and new catalogue styles. Some class families appear to be remnants of prior implementations.

A large CSS file is not inherently bad, but this one is starting to encode chronology rather than architecture.

### Recommendation

After the visual contract is agreed, reorganise styles by system responsibility, for example:

- `tokens.css`
- `base.css`
- `shell.css`
- `components.css`
- `entities.css`
- `tables.css`
- `operations.css`
- `topology.css`

Do **not** split first. First decide which styles are canonical, migrate components, then remove dead CSS and split the surviving system. Otherwise the project will merely distribute inconsistency across more files.

## 20.2 Dead/legacy styles should be removed deliberately

There are indications of older `summary-card`, dashboard prompt, profile/admin, network-member/asset-node and similar styles that no longer correspond to current feature implementations.

Add a cleanup task to identify unused selectors after migration. Removing them reduces accidental reuse and makes the canonical design language much easier for Codex and human contributors to understand.

## 20.3 Add UI architecture rules to contributor guidance

This is important if Atlas will continue to be built heavily with Codex.

Add concise rules to `AGENTS.md` or the frontend contributor documentation, for example:

- never introduce a new font size, radius or status colour without extending a token;
- use `PageHeader` for every application page;
- use `EntityIdentity` for first-class entities;
- use `EntityCollection` and `SearchFilterBar` for first-class entity browse pages, with domain-specific row composition;
- use `DataTable` for reference/admin datasets;
- use `StatusIndicator` rather than feature-specific status CSS;
- never use raw Unicode glyphs as icon-only controls;
- no user-facing sample/dev/roadmap copy without an explicit feature-state component;
- every new component must support keyboard focus, dark mode and mobile behaviour.

This will materially improve the quality of future AI-assisted implementation because the model will have a bounded visual grammar to follow.

---

# 22. Recommended Atlas UI foundation

The following is the design-system contract I would establish before doing page-by-page cleanup.

## 21.1 Tokens

### Typography

- font family
- H1/H2/H3/body/compact/label/meta sizes
- standard weights 400/500/600/700
- line heights

### Spacing

- 4 / 8 / 12 / 16 / 20 / 24 / 32

### Radius

- control 7
- surface 10
- overlay 12
- pill 999

### Controls

- 36px normal height
- 40–44px touch/large height

### Widths

Named page-width variants:

- `standard` — ordinary forms/details;
- `wide` — tables/catalogues;
- `canvas` — graph/topology.

Do not encode these only through unrelated feature classes.

## 21.2 Core components

### `PageHeader`

Context/breadcrumb + optional identity + H1 + description + actions + metadata.

### `EntityIdentity`

One API, entity-aware resolver, consistent optical box.

### `StatusIndicator`

Central semantic registry, dot/badge/text display variants.

### `EntityCollection` / `EntityCollectionRow`

Shared browse/list behaviour, loading/empty/error states, responsive layout and row interaction with entity-specific composition slots. It standardises behaviour without forcing identical visual rows.

### `DataTable`

Reference/admin/operational datasets.

### `Section`

Heading, optional description/actions, content; flat by default.

### `Surface`

Meaningful bordered grouping; standard padding/radius.

### `Button` / `IconButton`

All action semantics and focus behaviour.

### `SearchFilterBar`

Collapsed/expanded search, quick filters, advanced filters, active-filter state, Clear/reset, keyboard behaviour, responsive layout and URL/query-state conventions. Pages configure filters; they do not rebuild the shell.

### `EmptyState`

Title, explanation, optional primary action; no ad-hoc empty paragraphs.

### `Notice`

Info/success/warning/error, with consistent icon/semantic colour.

---

# 23. Page-family target state

## 22.1 Dashboard

**Keep:** compact operations-oriented composition.  
**Change:** use standard H1/type tokens, standard Section/Surface primitives, ensure all entity references use shared identity/status.  
**Avoid:** making dashboard cards a separate global visual system.

## 22.2 Assets

**Highest-value migration.**

- preserve the existing icon-rich Asset visual identity while migrating search/filtering, typography, row structure, responsiveness and interaction behaviour to the shared Entity Collection framework;
- migrate detail to shared entity-detail shell;
- retain real/cached Asset icon logic;
- standardise status/completeness presentation;
- remove page-specific heading/filter conventions.

## 22.3 Services

- keep the cleaner catalogue interaction model but enrich it with the shared Atlas entity-identity treatment so Services do not become visually bland;
- reduce description typography to strengthen title hierarchy;
- add inherited Service Type presentation identity;
- replace generic globe mark on detail/catalogue once identity is available;
- align exact H1/header scale with all pages.

## 22.4 Business Functions

- keep catalogue/detail architecture but bring its visual identity up to the same Atlas standard as Assets and Services;
- add deterministic auto-assigned presentation identity and picker;
- standardise create/edit form header and icon button;
- use exact same catalogue spacing/type hierarchy as Services.

## 22.5 Networks

- retain presentation identity model;
- align list/table decision with how users browse Networks. If Networks are increasingly first-class topology entities, consider moving them to the entity catalogue family; if the principal task is VLAN/network record administration, a table can remain appropriate.

## 22.6 Knowledge Graph

- preserve specialised canvas;
- standardise outer PageHeader and inspector entity identity;
- ensure relationship/status labels use central semantics;
- utility controls use shared icons/buttons.

## 22.7 Infrastructure Topology

- preserve specialised canvas and existing presentation identities;
- replace raw Asset status strings with `StatusIndicator` where state is presented;
- standardise inspectors and network/asset identity treatment;
- replace Unicode sorting/control glyphs;
- align header with standard canvas PageHeader variant.

## 22.8 Changes

- keep timeline presentation;
- align filter bar to shared FilterBar;
- status/severity through central registry;
- use type tokens rather than feature-specific micro scales where possible.

## 22.9 Knowledge Gaps

- retain specialised remediation card where it conveys workflow;
- correct H2/H3 hierarchy;
- reduce badge density;
- share status/priority semantics;
- use standard Section/Surface/button primitives.

## 22.10 Reconciliation

- retain specialised compare/decision layout;
- normalise heading/body type and surface radius;
- share FilterBar/status/buttons;
- ensure compare values are visually data, not another independent card system.

## 22.11 Discovery Runs / Simulate Discovery

- standard PageHeader;
- DataTable for run records where column comparison matters;
- common status registry;
- deliberate empty/loading/progress states.

## 22.12 Admin / Reference Data

- keep `CrudScreen` as the shared foundation;
- migrate its table to production `DataTable`;
- standardise create/edit form surface;
- use PresentationPicker for all bounded icon/accent settings;
- avoid one-off admin page layouts unless functionally necessary.

## 22.13 Audit / Users / System Settings

These are bespoke relative to generic CrudScreen and should be checked against the same admin header/table/form contract. System Settings in particular should remove future-feature placeholder language.

## 22.14 Profile

Keep visually simple. It should use standard PageHeader, Section and form/control tokens rather than retaining a unique profile-card heading scale.

## 22.15 Login

The login screen can retain a distinct brand composition, but use the same loaded font, button/input primitives and accessibility states as the main application. Distinct brand context should not mean distinct control behaviour.

---

# 24. Proposed cleanup sequence

The order matters. A page-by-page redesign before the primitives are fixed will create more duplicate styling.

## Phase 0 — Baseline and visual safety net

1. Define representative routes for visual regression.
2. Capture desktop/mobile light/dark baselines.
3. Add a UI cleanup branch and keep feature work separate where practical.
4. Identify all current selectors/components that will be replaced.

## Phase 1 — Foundation

1. Load the chosen font deterministically.
2. Add typography/spacing/radius/control tokens.
3. Normalise page width variants.
4. Add universal focus-visible behaviour.
5. Build/refine Button and IconButton.
6. Add SVG utility icons.

## Phase 2 — Common information grammar

1. Expand `PageHeader`.
2. Create the central status registry + StatusIndicator.
3. Create the unified `EntityIdentity` resolver.
4. Extend presentation identity to Service Types and Business Functions.
5. Standardise Section/Surface/EmptyState/Notice.

## Phase 3 — Lists and tables

1. Build/refine `EntityCollection` and `SearchFilterBar` as shared primitives.
2. Refine shared typography and identity spacing using the Asset page as the richer visual baseline.
3. Migrate Asset search/filtering and row structure without flattening Asset identity.
4. Apply the same framework to Services and Business Functions while retaining domain-specific presentation.
5. Decide Network browse pattern.
6. Build production DataTable.
7. Migrate CrudScreen/admin/reference tables.
8. Migrate specialised tables opportunistically.

## Phase 4 — Details

1. Migrate Asset detail to shared entity-detail shell.
2. Finish Service/Business Function identity integration.
3. Align edit/new pages with common header/form patterns.
4. Normalise metadata/status/completeness presentation.

## Phase 5 — Operational/specialised experiences

1. Dashboard.
2. Knowledge Graph.
3. Topology.
4. Changes.
5. Knowledge Gaps.
6. Reconciliation.
7. Discovery.

The intention is not to flatten their specialised workflows. Only migrate common visual/interaction concerns.

## Phase 6 — Production polish

1. Remove mock/sample/dev labels.
2. Hide or formalise unavailable settings.
3. Copy/capitalisation pass.
4. Remove dead CSS.
5. Reorganise CSS by system responsibility.
6. Full responsive/light/dark/custom-accent/keyboard review.
7. Cross-browser review.
8. Update frontend contributor guidance and UI tests.

---

# 25. Prioritised backlog

## P0 — Establish before broad visual cleanup

### P0.1 Deterministic typography

Load the chosen font and replace ad-hoc size/weight values with tokens.

### P0.2 One PageHeader

Eliminate 27px-vs-30px page-heading drift and move actions/context/identity into the common header contract.

### P0.3 Unified entity identity

- Asset: cached/type/generic image chain;
- Service: inherit icon/accent from Service Type;
- Business Function: stored auto-assigned icon/accent with picker;
- Network: existing presentation identity;
- same visual component in lists, details, graph/topology inspectors and dashboard.

### P0.4 Core entity collection consistency

Build one reusable Entity Collection + SearchFilterBar framework. Use Assets as the visual-identity baseline and Services/Business Functions as the interaction/filter baseline. Standardise the underlying code, behaviour and tokens without forcing identical row designs.

### P0.5 Remove development scaffolding from user UI

Local-development footer, sample integrations, roadmap-style settings placeholders.

## P1 — Major consistency improvements

### P1.1 Central status semantics

One state → one label/tone everywhere. Fix maintenance mismatch.

### P1.2 Shared detail shell

Migrate Asset detail and standardise entity metadata/status/actions.

### P1.3 Button/IconButton/focus system

Consistent sizes, focus rings, SVG controls and accessible labels.

### P1.4 Production DataTable

Replace repeated raw table grammar and remove sample-specific semantics.

### P1.5 Surface hierarchy

Reduce card variants; establish Section/Surface/Overlay.

### P1.6 Copy and naming rules

Sentence-case action/UI policy and explicit product terminology.

## P2 — Hardening and refinement

### P2.1 Responsive visual QA

Defined viewport matrix and touch-target review.

### P2.2 CSS archaeology

Delete legacy/unreferenced selectors after migrations.

### P2.3 CSS architecture

Split by responsibility after canonical styles are settled.

### P2.4 Visual regression tests

Representative core pages in light/dark and desktop/mobile.

---

# 26. Concrete design decisions recommended for Atlas

To make the future cleanup executable rather than subjective, I recommend adopting these decisions as the initial UI specification.

## Typography

- Self-host/load **Inter** deterministically.
- H1: 28/700.
- H2: 16/600.
- H3: 14/600.
- Body: 14/400.
- Compact/table: 13/400.
- Catalogue name: 15/600.
- Catalogue description: 13/400.
- Meta: 11–12/500.
- Form label: 12/600.
- Limit standard weights to 400/500/600/700.

## Shape

- Control radius: 7px.
- Surface radius: 10px.
- Overlay radius: 12px.
- Pills: 999px only when the content genuinely behaves as a tag/badge.

## Density

- Normal control height: 36px.
- List rows: 14–16px vertical padding.
- Table rows: 44–48px.
- Surface padding: 16–20px.
- Page section spacing: 24px minimum.

## Colour

- User accent: navigation/actions/focus only.
- Presentation accent: entity identity only.
- Semantic palette: status/severity only.
- Never recolour entity identity to show status.

## Icons

- Bounded internal SVG/presentation registry.
- Asset imagery may use cached discovered/vendor artwork through the existing safe path.
- No arbitrary user URL icon model for standard entity identity.
- No Unicode characters as icon-only controls.

## Entity collections

- Asset, Service and Business Function use the shared `EntityCollection` + `SearchFilterBar` foundation.
- Each domain composes its own identity and metadata treatment; consistency comes from shared primitives, tokens and behaviour rather than visual sameness.
- Asset icons remain prominent and recognisable.
- Services and Business Functions gain equally deliberate icon/colour identity without imitating Asset imagery.
- Reference/admin datasets use the DataTable family.
- Specialised workflows remain purpose-built using common primitives.

## Status

- recorded operational state = dot + label;
- severity/review/workflow = badge;
- lifecycle = subdued tag/text;
- completeness = progress/percentage.

---

# 27. Definition of done for the design-cleanup release

The cleanup should not be considered complete merely because individual screenshots look good.

## Global consistency

- [ ] Every standard route uses the canonical PageHeader.
- [ ] No ordinary page changes H1 sizing through a feature wrapper.
- [ ] Heading hierarchy is semantically and visually correct.
- [ ] All font sizes/weights come from the approved type scale, with documented exceptions only.
- [ ] All common radii/spacing/control heights use tokens.
- [ ] No user-facing “sample”, “local development” or roadmap placeholder copy remains unless explicitly intentional.

## Entities

- [ ] Assets, Services and Business Functions use the same Entity Collection/SearchFilter foundation while retaining appropriate domain-specific visual identity.
- [ ] All first-class entities render through `EntityIdentity`.
- [ ] Services inherit identity from Service Type.
- [ ] Business Functions have deterministic default identity and picker support.
- [ ] Asset icon fallback behaviour remains intact.
- [ ] Identity colour is never used as status colour.

## Status

- [ ] One central registry owns labels and semantic tones.
- [ ] Maintenance and every other state are visually identical wherever displayed.
- [ ] Raw status strings are not used where StatusIndicator is expected.
- [ ] Badge use is restrained and semantically defined.

## Controls/accessibility

- [ ] Every icon-only button has an accessible name.
- [ ] All interactive elements show a consistent keyboard focus state.
- [ ] Utility controls use SVG icons rather than Unicode glyphs.
- [ ] Primary controls meet target hit sizes.
- [ ] Reduced-motion behaviour is retained.

## Responsive

- [ ] Representative pages verified at 1440, 1024, 768–900 and 390px.
- [ ] Tables overflow intentionally without clipping controls.
- [ ] Long titles/descriptions do not break layouts.
- [ ] Navigation remains usable at tablet breakpoint.

## Theme

- [ ] Light mode reviewed.
- [ ] Dark mode reviewed.
- [ ] Default accent reviewed.
- [ ] At least two custom accent colours reviewed for contrast and visual balance.

## States

- [ ] Loading state exists for all core page families.
- [ ] Empty state exists and uses the shared primitive.
- [ ] Error/permission state is deliberate.
- [ ] Missing/fallback entity icon state is deliberate.

## Engineering

- [ ] Legacy/dead CSS removed after migration.
- [ ] UI architecture rules documented for Codex/human contributors.
- [ ] Tests enforce key primitives and status/identity mappings.
- [ ] Shared primitives own repeated behaviour; page-specific CSS/logic is not duplicating search, header, status, control or identity behaviour.
- [ ] Component APIs remain composable and do not collapse into one oversized generic entity component.
- [ ] Tenant/workspace context assumptions are documented and do not require a future UI rewrite for MSP mode.
- [ ] Representative visual regression coverage added.

---

# 28. Suggested UI architecture rules for future Codex prompts

These rules would materially reduce future UI drift:

1. **Reuse before creation.** Search for an existing Atlas primitive before adding a new page-specific visual component.
2. **No arbitrary visual constants.** New font size, radius, semantic colour or standard control height requires a token/design-system reason.
3. **Every page uses PageHeader.** Specialised pages may select a documented variant but must not recreate the header.
4. **Every first-class entity uses EntityIdentity.** Do not hand-render generic icons or identity colour in feature pages.
5. **Status comes from the registry.** Do not map status strings to colours in page CSS.
6. **Entity browse pages use EntityCollection + SearchFilterBar.** Domain rows may differ visually, but search/filter, spacing, responsive behaviour, loading/empty/error states and interaction conventions must come from the shared primitives. Tables are for datasets where column comparison is the user task.
7. **Reference/admin datasets use DataTable.** Do not introduce raw tables in new CRUD pages.
8. **Use SVG utility icons.** Do not use Unicode glyphs for UI controls.
9. **All icon-only controls require an accessible label.**
10. **Every new/changed component must work in light/dark mode, keyboard navigation and 390px mobile width.**
11. **Do not add generic cards by default.** Use spacing/sections first; Surface only where grouping is meaningful.
12. **Do not solve inconsistency with one-off page styling.** Prefer existing Atlas primitives. If a visual or interaction pattern appears twice, evaluate whether it belongs in the shared component layer.
13. **Prefer composition over giant generic components.** Do not create a single `EntityPage`/`EntityRow` API with dozens of mode/variant props when small domain components can compose shared primitives more clearly.
14. **Keep tenant context separate from entity and status semantics.** Components should be future multi-tenant safe without adding premature MSP chrome.
15. **No development scaffolding in production UI.** Mock, sample, future-roadmap and local-environment text must be feature-flagged or intentionally designed.

---

# 29. Final design direction

Atlas should not chase a consumer-app aesthetic or a highly decorative SaaS dashboard style. Nor should consistency flatten it into a generic AI-generated admin interface. Its strongest possible identity is a **professional operational knowledge system**: understated, precise, visually distinctive and exceptionally coherent.

The Asset experience demonstrates that recognisable icons and stronger entity identity improve visual appeal and scanability. That richness should become part of the Atlas design language, not be removed. Services and Business Functions should reach the same level of deliberate identity through their own icon/colour semantics.

The visual hierarchy should feel calm enough that topology, relationships, completeness and operational state become the interesting parts of the screen. Entity icons and bounded presentation colours can give the product personality without turning it into a rainbow. Tables should be dense where comparison matters; entity collections should be spacious enough for recognition where navigation matters; graph and topology surfaces can remain visually specialised while sharing the same entity/status language.

Most importantly, the consistency must exist in the **code architecture** as well as the screenshots. Reusable tokens, primitives and domain components should make the correct Atlas treatment the easiest implementation path for future contributors and Codex.

The cleanup should therefore be judged by a simple test:

> A user should be able to move from Dashboard → Assets → Asset detail → Service → Business Function → Knowledge Graph → Topology without encountering a change in the application’s visual grammar, even though each screen performs a different job.

Atlas is close enough that this does not require a wholesale redesign. It requires **consolidation, tokenisation and disciplined reuse**. That is the right cleanup before adding another major layer of product functionality.

