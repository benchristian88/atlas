# Atlas Impact UI Architecture and Design System

**Status:** Canonical frontend UI architecture guidance  
**Applies to:** `apps/web` and all future Atlas Impact web UI work  
**Purpose:** Preserve a coherent Atlas visual language and reusable implementation architecture as the product grows.

---

## 1. Authority and intent

This document is the long-lived UI architecture standard for Atlas Impact. It defines the rules future human and AI contributors should follow when creating or modifying web UI.

Dated UI reviews and implementation prompts are historical evidence. This document is the canonical design-system guidance unless a later accepted architecture decision explicitly supersedes it.

Atlas consistency must exist in **code architecture and interaction behaviour**, not merely in screenshots. New pages should look and behave like Atlas because they reuse shared tokens, primitives and domain components—not because a developer copies CSS from another page.

The target is a professional operational knowledge system: modern, restrained, information-dense, accessible and visually distinctive without becoming decorative or generic SaaS UI.

---

## 2. Core principles

### 2.1 Reuse before creation

Before creating UI markup, CSS or a new component, inspect the existing Atlas primitives and domain components. Extend an existing abstraction where it is genuinely the same concern.

If a visual or interaction pattern appears more than once, evaluate whether it belongs in the shared component layer.

### 2.2 Consistency does not mean visual sameness

Assets, Services, Business Functions, Networks, topology and graphs perform different jobs and do not need identical layouts.

Shared concerns must be consistent:

- typography;
- spacing;
- control dimensions;
- focus treatment;
- status semantics;
- entity identity contract;
- search/filter behaviour;
- loading, empty and error states;
- responsive rules;
- accessibility;
- tenant/workspace context.

Domain-specific presentation may remain distinct where it improves recognition or usability.

### 2.3 Preserve Atlas visual identity

Do not flatten Atlas into a generic admin dashboard.

The Asset experience is the aesthetic reference for strong entity recognition: recognisable icons, restrained identity colour, readable hierarchy and useful density.

The current Services and Business Functions catalogue is the interaction reference for first-class entity browsing: linked rows, concise hierarchy, automatic search, quick filters, advanced filters, responsive behaviour and keyboard treatment.

The intended direction is to combine those strengths through reusable components.

### 2.4 Prefer composition over giant generic components

Use small primitives with clear responsibilities. Domain components should compose them.

Do not create a single `EntityPage`, `EntityRow` or equivalent component with dozens of flags and variants to handle unrelated domain behaviour.

### 2.5 Separate identity from state

Entity identity answers **what is this?** Operational state answers **what state is it in?**

Identity colour must never be repurposed as status/severity colour.

### 2.6 Tenant-aware, not tenant-styled

Atlas is expected to support MSP/multi-tenant use. Shared components must not assume a permanently single-customer context or globally unique display identity.

Tenant/workspace context is a separate application-shell concern. Do not tint entities by customer or encode tenant identity into operational status or entity identity colours.

---

## 3. Design tokens

Common visual values must be expressed through shared tokens rather than arbitrary page-level constants.

### 3.1 Typography

Use one deterministic application font strategy. Atlas loads Inter Variable from the pinned `@fontsource-variable/inter` package in `app/layout.js`. Font files are served by the application; builds and browsers do not fetch Google Fonts. The `--font-ui` token names the loaded font.

Approved standard scale:

| Role | Size | Weight | Line height |
| --- | ---: | ---: | ---: |
| Page H1 | 28px | 700 | 1.15 |
| Section H2 | 16px | 600 | 1.35 |
| Subsection H3 | 14px | 600 | 1.4 |
| Entity/list title | 15px | 600 | 1.35 |
| Body | 14px | 400 | 1.5 |
| Compact/table body | 13px | 400 | 1.45 |
| Form/metadata label | 12px | 600 | 1.35 |
| Secondary metadata | 11–12px | 500 | 1.35 |

Use 400/500/600/700 as the normal weight set. Avoid arbitrary sizes and synthesized weights such as 550/650/750 unless there is a documented, font-supported reason.

Semantic heading depth and visual hierarchy must agree. A nested H3 must not render more prominently than its parent H2.

### 3.2 Spacing

Use a bounded spacing scale. Prefer values derived from:

`4 / 8 / 12 / 16 / 20 / 24 / 32 / 40px`

Recommended defaults:

- list row vertical padding: 14–16px;
- table row height: 44–48px;
- surface padding: 16–20px;
- major page section spacing: at least 24px;
- normal control gap: 8–12px.

Do not introduce one-off spacing values to visually patch a page unless a documented layout constraint requires it.

### 3.3 Shape

- standard control radius: **7px**;
- standard surface radius: **10px**;
- overlay/dialog/popover radius: **12px**;
- pill radius: **999px** only for genuine tags, badges, chips or pill controls.

### 3.4 Controls

- normal control height: **36px**;
- interactive controls must have a visible `:focus-visible` state;
- icon-only controls require accessible names;
- control hit areas must remain usable on touch devices;
- disabled, loading and destructive states must be explicit.

### 3.5 Colour semantics

Keep these channels separate:

- **user accent:** primary actions, navigation emphasis and focus;
- **presentation identity:** entity/category/type recognition;
- **semantic status palette:** operational status, severity and warnings;
- **neutral palette:** structure, borders, surfaces and secondary text.

Do not rely on colour alone to convey state.

---

## 4. Component architecture

Atlas should maintain three layers.

### 4.1 Foundation tokens

Typography, spacing, radius, colours, control dimensions, focus, elevation and responsive breakpoints.

### 4.2 Shared UI primitives

The shared primitive layer should include or converge on:

- `PageHeader`
- `Button`
- `IconButton`
- `SearchFilterBar`
- `EntityCollection`
- `EntityCollectionRow`
- `EntityIdentity`
- `StatusIndicator`
- `DataTable`
- `Section`
- `Surface`
- `EmptyState`
- `Notice`
- common field/select/combobox patterns

These primitives own repeated behaviour as well as styling: focus handling, keyboard behaviour, accessibility labels, responsive collapse, loading/empty/error conventions, truncation and common spacing.

### 4.3 Domain components

Domain components should compose shared primitives while retaining genuine domain semantics, for example:

- `AssetIdentity`
- `ServiceIdentity`
- `BusinessFunctionIdentity`
- `NetworkIdentity`
- domain-specific entity rows or metadata renderers where needed.

Shared implementation must not erase useful differences between domains.

---

## 5. PageHeader

Every normal product route should use the canonical `PageHeader`.

It should support, as appropriate:

- title;
- concise description;
- optional eyebrow where it adds meaningful product context;
- primary action(s);
- optional metadata/context;
- a documented compact variant for canvas/graph-style screens.

Do not recreate page headings locally or alter H1 size through broad feature wrapper CSS.

Eyebrows should be purposeful, not a mandatory template decoration on every screen.

---

## 6. First-class entity collections

Assets, Services and Business Functions should use the same **Entity Collection architecture** while retaining domain-specific visual presentation.

### 6.1 Shared behaviour

The collection layer should own:

- page/list spacing;
- search/filter placement and behaviour;
- keyboard focus and row activation;
- loading/empty/error states;
- responsive collapse;
- consistent metadata hierarchy;
- row separators/surfaces;
- truncation and long-content handling;
- URL/query-state conventions where applicable.

### 6.2 Assets

Assets are the aesthetic baseline for strong entity recognition.

Preserve:

- cached/vendor/workload imagery;
- current safe fallback chain;
- prominent, recognisable identity;
- useful operational metadata.

Improve the surrounding search/filter architecture, typography, spacing and interaction consistency without flattening Asset rows into generic text records.

### 6.3 Services

The current Services catalogue interaction is an accepted baseline unless a specific task explicitly changes it.

Preserve the useful structure represented by the current implementation:

- prominent Service identity icon;
- clear Service name and concise description;
- useful relationship metadata;
- Service Type identity;
- operational status shown separately;
- search + type selector + expandable Filters model;
- quick-filter chips/counters and advanced filter controls where useful.

Services should inherit presentation identity from Service Type by default. Service Type presentation should use the same bounded icon/colour system used elsewhere rather than arbitrary free-text icon rendering.

### 6.4 Business Functions

Business Functions should use the same collection/search/filter foundation while retaining a deliberate Business Function identity.

Provide deterministic initial icon/colour assignment and allow a bounded presentation picker where configuration is appropriate.

Do not make Business Functions visually indistinguishable from Services; share the grammar, not every visual detail.

### 6.5 Networks and future first-class entities

When a new first-class browse page is introduced, first decide whether the user task is entity recognition/navigation or tabular comparison.

Use `EntityCollection` for the former and `DataTable` for the latter.

---

## 7. Search and filters

Search/filter behaviour is a product primitive, not a page-specific decoration.

`SearchFilterBar` should own:

- search input treatment;
- type/category selector where applicable;
- collapsed/expanded filter state;
- active-filter count;
- quick filters;
- advanced filters;
- clear/reset behaviour;
- responsive wrapping/collapse;
- keyboard navigation;
- consistent focus treatment;
- query/URL state conventions where appropriate.

Individual pages supply their available filters and domain-specific labels. They should not reimplement the shell.

The current Services/Business Functions search/filter layout is the interaction reference; the Asset page should migrate to the same behavioural framework while preserving its richer entity visual identity.

---

## 8. Entity identity and iconography

All first-class entities should render through a shared `EntityIdentity` contract.

### 8.1 Assets

Resolution order should preserve existing behaviour:

1. cached/discovered/vendor icon where available;
2. configured Asset Type/category presentation identity;
3. safe generic fallback.

### 8.2 Services

Default icon/colour comes from Service Type. Per-Service override should exist only if the product has a clear need for it.

### 8.3 Business Functions

Use deterministic default icon/colour identity, with bounded override support if enabled.

### 8.4 Networks

Use the existing bounded presentation identity mechanism.

### 8.5 Utility icons

Use a shared internal SVG/icon registry for controls and navigation. Do not use Unicode glyphs as icon-only UI controls.

Do not accept arbitrary external image URLs as a general identity system for standard entities.

---

## 9. Status and badges

Operational state semantics must come from one central registry rather than local CSS or component mappings.

The registry should own at least:

- canonical value;
- user-facing label;
- semantic tone;
- optional icon/dot treatment;
- accessibility label where needed.

Use the following presentation grammar:

- recorded operational state: **dot + label**;
- severity/review/workflow state: **badge**;
- lifecycle: **subdued tag/text**;
- completeness: **progress/percentage**.

The same status must render the same way everywhere. For example, `maintenance` cannot be warning-coloured on one screen and informational blue on another.

Status colour must never replace entity identity colour.

---

## 10. Tables

Use tables where column comparison is the principal task: administrative/reference datasets, audit records and genuinely tabular operational views.

Standardise through `DataTable` rather than introducing raw page-level tables.

The production table primitive should own:

- typography and row density;
- header treatment;
- alignment;
- row hover/focus;
- empty/loading/error states;
- responsive overflow;
- actions column conventions;
- accessible table semantics.

Do not use a table merely because a dataset has fields. First-class browsable entities should usually use the Entity Collection family.

---

## 11. Sections and surfaces

Avoid wrapping every block in a decorative card.

Use:

- normal page spacing for simple grouping;
- `Section` for semantic page structure;
- `Surface` only when a bordered/raised container materially helps grouping;
- overlays/dialog surfaces for floating interaction.

Keep shadows restrained. Atlas should feel like operational software, not a dashboard template.

---

## 12. Detail pages

Asset, Service and Business Function details should converge on a shared entity-detail shell.

The shared shell should standardise:

- page/entity header;
- entity identity;
- primary status;
- primary actions;
- metadata groups;
- section spacing;
- empty states;
- edit/delete placement;
- responsive behaviour.

Domain-specific detail sections remain domain-specific.

Do not preserve an older detail-page visual system solely because the domain predates the newer shell.

---

## 13. Forms and bounded presentation settings

Standard fields should use shared form primitives and consistent label/help/error styling.

Presentation settings such as icon and identity colour should use a bounded picker model rather than free-text visual configuration.

Validation must be visible, accessible and consistent.

---

## 14. Multi-tenant / MSP readiness

UI components must not require a redesign when Atlas later exposes multiple customers to an MSP operator.

Requirements:

- tenant/workspace context remains an application-shell concern;
- tenant context must be persistent and unmistakable when multi-tenant operation is active;
- entity identity does not encode tenant identity;
- status colour does not encode tenant identity;
- component state, route construction and cache/query keys should not assume a display name is globally unique;
- authorization remains a backend/API concern—frontend tenant selection is not a security boundary.

Do not add premature MSP chrome while the product is operating in a simpler mode. Build tenant-safe boundaries now.

---

## 15. Responsive and accessibility requirements

Every new or materially changed shared component must be reviewed at representative widths:

- 1440px desktop;
- 1024px compact desktop/tablet landscape;
- 768–900px tablet;
- 390px mobile.

Requirements:

- no clipped primary actions;
- tables overflow intentionally;
- long names/descriptions do not break layout;
- search/filter controls collapse predictably;
- keyboard focus remains visible;
- icon-only controls have accessible names;
- semantic HTML and ARIA are used appropriately;
- state is not communicated by colour alone;
- `prefers-reduced-motion` support is preserved.

---

## 16. Theme requirements

Every shared component must work in:

- light mode;
- dark mode;
- default accent;
- at least two custom accent colours during acceptance testing.

User accent is for actions/navigation/focus. It must not override status semantics or entity presentation identity.

---

## 17. Copy and microcopy

Use sentence case for ordinary UI text.

Keep descriptions short and task-oriented. Avoid generic explanatory filler that makes pages feel templated.

Use one naming/capitalisation convention for equivalent actions across the product, for example `Add asset`, `Add service`, `Add business function` or another intentionally selected convention—not a mixture.

User-facing development scaffolding, sample labels, roadmap placeholders and local-development notices must be removed, feature-flagged or intentionally designed.

---

## 18. CSS and styling architecture

Do not solve inconsistency by adding more page-specific CSS to `globals.css`.

During migration:

1. introduce/normalise design tokens;
2. move repeated styles behind component-level classes/primitives;
3. migrate pages onto those primitives;
4. delete superseded selectors only after usage is removed and tests pass.

Do not perform blind CSS deletion. Historical styles may still support routes not obvious from a single page.

New arbitrary font sizes, radii, semantic colours or control heights require an explicit design-system reason.

---

## 19. Testing and visual safety net

UI changes should include appropriate automated coverage following current repository conventions.

At minimum, test the contracts that are easy to regress programmatically:

- entity identity resolution/fallback;
- status-to-tone mapping;
- filter/search state behaviour;
- key component accessibility attributes;
- responsive state logic where implemented in JS;
- retained Asset icon fallback behaviour.

Maintain representative browser/manual visual acceptance coverage for:

- Dashboard;
- Assets;
- Asset detail;
- Services;
- Business Functions;
- Knowledge Graph;
- Topology;
- one admin/reference table;
- login/profile/shell.

Review light/dark modes and representative viewport sizes.

---

## 20. Rules for future contributors and Codex

1. Reuse an Atlas primitive before creating a page-specific replacement.
2. Do not introduce arbitrary visual constants where a design token exists.
3. Every normal page uses `PageHeader`.
4. Every first-class entity uses `EntityIdentity` or a domain component built on it.
5. Status comes from the central status registry.
6. Entity browse pages use `EntityCollection` + `SearchFilterBar` unless the user task is genuinely tabular.
7. Reference/admin datasets use `DataTable`.
8. Use shared SVG utility icons, not Unicode controls.
9. All icon-only controls require accessible labels.
10. Test new/changed shared components in light/dark mode, keyboard navigation and 390px mobile width.
11. Do not add cards by default; use spacing and sections first.
12. Do not fix systemic inconsistency with one-off page styling.
13. Prefer composition over oversized generic components with many mode flags.
14. Keep tenant context separate from entity identity and status semantics.
15. Do not expose development scaffolding in production UI.
16. Preserve current accepted Services/Business Functions catalogue interaction unless a task explicitly changes that design.
17. Preserve the recognisable Asset icon/identity experience while migrating its surrounding controls to shared primitives.
18. When changing a shared UI rule, update this document in the same change.

---

## 21. Recommended migration sequence

### Phase 0 — Baseline

- identify representative routes;
- capture light/dark and desktop/mobile baselines;
- inventory selectors/components being replaced;
- keep unrelated feature work out of the cleanup where practical.

### Phase 1 — Foundation

- deterministic application font;
- typography/spacing/radius/control tokens;
- width/layout tokens;
- universal focus-visible treatment;
- `Button` and `IconButton`;
- shared utility SVG icons.

### Phase 2 — Information grammar

- canonical `PageHeader`;
- status registry + `StatusIndicator`;
- `EntityIdentity` contract;
- bounded presentation identity for Service Types and Business Functions;
- `Section`, `Surface`, `EmptyState`, `Notice`.

### Phase 3 — Collections and tables

- shared `SearchFilterBar`;
- shared `EntityCollection` foundation;
- migrate Asset search/filter/rows without losing Asset identity;
- refactor Services/Business Functions onto shared internals without visually regressing the accepted catalogue experience;
- production `DataTable`;
- migrate admin/reference tables.

### Phase 4 — Detail pages

- shared entity-detail shell;
- Asset detail migration;
- Service/Business Function identity integration;
- common form/header/status/completeness presentation.

### Phase 5 — Specialised operational views

Apply shared concerns to Dashboard, Knowledge Graph, Topology, Changes, Knowledge Gaps, Reconciliation and Discovery without flattening their specialised workflows.

### Phase 6 — Production polish

- remove development/sample placeholders;
- copy/capitalisation sweep;
- dead CSS removal;
- responsive and dark-mode visual acceptance;
- visual regression coverage where practical.

---

## 22. Definition of done

A UI-system cleanup is not complete because a few screenshots look better.

### Global

- all standard product routes use the canonical `PageHeader` (Login may retain its labelled authentication heading);
- typography and common dimensions come from the approved tokens;
- heading hierarchy is semantically correct;
- no broad feature wrapper silently changes ordinary heading scale;
- no unintended development/sample copy is visible.

### Entities

- Assets, Services and Business Functions share the Entity Collection/SearchFilter foundation;
- their domain-specific identity remains intentional and recognisable;
- all first-class entities render through the identity contract;
- Service identity is derived from Service Type by default;
- Business Functions have deterministic presentation identity;
- Asset icon fallback behaviour remains intact;
- identity colour is never status colour.

### Status

- one central registry owns labels and semantic tones;
- the same status renders consistently everywhere;
- feature pages do not locally map raw status strings to colours.

### Controls and accessibility

- icon-only controls have accessible names;
- focus-visible treatment is consistent;
- shared utility icons replace Unicode UI controls;
- target hit areas remain usable;
- reduced-motion behaviour is preserved.

### Responsive and theme

- representative routes are verified at 1440, 1024, 768–900 and 390px;
- light and dark mode are both reviewed;
- at least two custom accent colours are checked;
- long text, empty states and errors do not break layout.

### Engineering

- repeated behaviour is implemented in shared primitives rather than page-specific CSS/logic;
- component APIs remain composable rather than over-generalised;
- superseded CSS is removed after migration;
- tests cover key identity/status/filter contracts;
- tenant/workspace assumptions are safe for future MSP mode;
- this architecture guide and relevant repository contributor guidance are updated when shared UI rules change.

---

## 23. Product-level acceptance test

Atlas should pass this simple test:

> A user can move from Dashboard → Assets → Asset detail → Service → Business Function → Knowledge Graph → Topology without encountering a change in the application's visual grammar, even though each screen performs a different job.

The goal is not uniformity. It is a coherent product whose shared standards are implemented once and reused everywhere.


## 23. Implementation contracts and deliberate exceptions

- Tokens live in `app/globals.css`; `app/presentation.css` owns the bounded entity palette. Add common rules to their owning sections rather than appending overrides.
- `CatalogueFilters` is a compatibility export of `SearchFilterBar`; `EntityCatalogue` is a compatibility export of `EntityCollection`. These are one implementation, not competing systems. Domain row components compose `CatalogueRow`.
- `RecordedStatus`, `EntityMark` and `StatusBadge` delegate to the shared identity/status contracts. Legacy CSS class names are hooks, not state-to-colour registries. Maintenance always has the informational tone.
- `EntityDetailHeader` supports Assets, Services and Business Functions. `EntitySection` composes `Section`; use `Surface` only where bordered grouping adds meaning.
- `Button` accepts primary, secondary, quiet and destructive variants, native button types, a link destination, disabled and loading state. `IconButton` requires a label and uses the shared SVG registry. Existing specialised selectable graph nodes remain native controls.
- `DataTable` uses a caption, scoped column headers, stable record IDs, optional action renderers and keyboard-accessible horizontal overflow. `CrudScreen` passes existing capability checks through its actions renderer. Related-record renderers retain their existing arguments.
- Search typing uses a 300 ms debounce; discrete changes apply immediately. Clear, URL navigation and workspace changes cancel pending searches. Pages retain their existing query codecs and server-side filters; components never implement tenancy or authorization.
- Business Function identity defaults are derived from durable UUIDs, never names or tenant colour. Optional stored overrides use the existing bounded picker. Service Types retain historical icon strings through the API for compatibility; new UI configuration is bounded. Nullable new presentation fields preserve existing records without remapping them.
- Asset image resolution retains authenticated cached images and managed type imagery. Bounded type/category presentation is the next fallback, followed by the generic image for consumers without presentation metadata. External Asset source URLs are never rendered directly.
- Graph projection includes optional presentation fields for already-authorized nodes. These do not alter reachability, dependency meaning or authorization.
- Networks remain a reference table because VLAN/CIDR comparison is its current primary task. Canvas geometry, brand lockups, authentication composition, readable monospace data and topology/export layout constants may use specialised dimensions.
- The dated [September review](../history/product-reviews/atlas-ui-system-review-2026-09.md) records rationale, not implementation status or new requirements. This guide is the canonical future standard.

The acceptance matrix covers 1440, 1024, 800 and 390 px; light/dark themes; default, blue and purple action accents; keyboard focus, long content, table overflow, errors and fallback identity. See [UI system acceptance](../testing/ui-system.md), `apps/web/scripts/check-ui-system-browser.mjs` and the existing entity, Asset icon, operations and topology scripts. Record actual validation results separately from this stable standard.
