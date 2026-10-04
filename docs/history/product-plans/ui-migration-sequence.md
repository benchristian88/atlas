> **Historical implementation plan.** Original UI migration sequencing, retained for traceability. The active UI architecture specifies current contracts.

# UI migration sequence

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

