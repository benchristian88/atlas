import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
const require = createRequire(import.meta.url);
const { transformSync } = require("next/dist/compiled/babel/core");
const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
// Exercise actual JSX with Next's existing compiler, without a new dependency.
function component(path, imports) {
  const { code } = transformSync(source(path), { babelrc: false, configFile: false,
    presets: [[require("next/dist/compiled/babel/preset-react"), { runtime: "classic" }]],
    plugins: [require("next/dist/compiled/babel/plugin-transform-modules-commonjs")],
  });
  const exports = {};
  Function("require", "exports", "React", code)((name) => imports[name], exports, React);
  return exports;
}
const catalogue = component("../components/entity-catalogue.js", {
  "next/link": { __esModule: true, default: ({ children, ...props }) => React.createElement("a", props, children) },
  "./operations-primitives": component("../components/operations-primitives.js", { "../lib/operations-experience.mjs": {} }),
});
const render = (name, props) => renderToStaticMarkup(React.createElement(catalogue[name], props));
const service = { id: "dns", name: "DNS", description: "Resolves names", purpose: "Legacy purpose", service_type_name: "Infrastructure Service", operational_status: "operational", lifecycle_status: "active", asset_dependency_count: 3, business_function_count: 1, owner_name: "Hidden owner", criticality_name: "Hidden criticality", rto_minutes: 60, completeness_status: "incomplete" };
test("Service identity, health, type and relationships render without administrative fields", () => {
  const html = render("ServiceCatalogueRow", { service });
  for (const text of ["DNS", "Resolves names", "Infrastructure Service", "Operational", "3 assets · 1 business function"]) assert.ok(html.includes(text), text);
  for (const text of ["Hidden owner", "Hidden criticality", "RTO", "incomplete", "Active", "Legacy purpose"]) assert.ok(!html.includes(text), text);
  assert.match(html, /<a class="catalogue-row" href="\/services\/dns">/);
  assert.doesNotMatch(html, /<button|tabindex="-1"|onclick/);
});
test("Service grammar, health values, fallback descriptions and exceptional lifecycle", () => {
  for (const [a, b, expected] of [[1, 0, "1 asset"], [2, 3, "2 assets · 3 business functions"], [0, 1, "1 business function"]]) {
    const html = render("ServiceCatalogueRow", { service: { ...service, asset_dependency_count: a, business_function_count: b } });
    assert.ok(html.includes(expected)); assert.doesNotMatch(html, /0 assets|0 business functions/);
  }
  for (const health of ["unknown", "operational", "degraded", "outage", "maintenance"]) {
    const html = render("ServiceCatalogueRow", { service: { ...service, operational_status: health } });
    assert.ok(html.includes(`status-${health}`)); assert.ok(html.includes(health[0].toUpperCase() + health.slice(1)));
  }
  assert.match(render("ServiceCatalogueRow", { service: { ...service, description: null } }), /Legacy purpose/);
  assert.match(render("ServiceCatalogueRow", { service: { ...service, archived_at: "2026-09-01" } }), /Archived/);
});
test("Business Function description, service count, state and native keyboard-accessible links", () => {
  for (const count of [0, 1, 6]) {
    const html = render("BusinessFunctionCatalogueRow", { item: { id: "home", name: "Home", description: "Keeps us connected", service_count: count, active: true, owner_name: "Hidden owner", criticality_name: "Hidden criticality" } });
    for (const text of ["Home", "Keeps us connected", `${count} service${count === 1 ? "" : "s"}`, "Active"]) assert.ok(html.includes(text));
    assert.match(html, /<a class="catalogue-row" href="\/business-functions\/home">/);
    assert.doesNotMatch(html, /Hidden owner|Hidden criticality|<button|tabindex="-1"/);
  }
  assert.match(render("BusinessFunctionCatalogueRow", { item: { id: "old", name: "Old", active: false, service_count: 0 } }), /Archived/);
});
test("Catalogue loading, error, empty and populated states remain distinct", () => {
  const props = { label: "Services", count: 0, empty: "No matches", children: React.createElement("li", null, "Visible row") };
  const loading = render("EntityCatalogue", { ...props, loading: true });
  assert.match(loading, /aria-busy="true"/); assert.match(loading, /Loading Services/); assert.match(loading, /disabled/); assert.doesNotMatch(loading, /No matches|Visible row/);
  const error = render("EntityCatalogue", { ...props, error: "Failed" });
  assert.match(error, /could not be loaded/); assert.doesNotMatch(error, /No matches|Visible row/);
  assert.match(render("EntityCatalogue", props), /No matches/);
  assert.match(render("EntityCatalogue", { ...props, count: 1 }), /<ul class="catalogue-list"><li>Visible row/);
});
test("Pages retain scoped API search/type filters and active-only Business Functions by default", () => {
  const services = source("../app/services/page.js"); const functions = source("../app/business-functions/page.js");
  assert.match(services, /params.set\("search", filters.search\)/);
  assert.match(services, /params.set\("service_type_id", filters.serviceTypeId\)/);
  assert.match(services, /router.replace/);
  assert.match(services, /update\(\{ serviceTypeId: event.target.value \}\)/);
  assert.match(functions, /\[showArchived, setShowArchived\] = useState\(false\)/);
  assert.match(functions, /active_only: String\(!showArchived\), search/);
  assert.match(functions, /useCatalogueSearch\(search, setSearch\)/);
  assert.match(functions, /setShowArchived\(event.target.checked\)/);
  for (const page of [services, functions]) {
    assert.match(page, /hasPermissionInContext/); assert.match(page, /role="alert"/);
    assert.match(page, /<CatalogueFilters/); assert.match(page, /<EntityCatalogue/); assert.doesNotMatch(page, /<table|<th>/);
  }
});
test("Catalogue focus and mobile layout use theme tokens", () => {
  const css = source("../app/globals.css");
  assert.match(css, /\.catalogue-row:focus-visible/);
  assert.match(css, /\.catalogue-health \.status-outage \{ background: var\(--danger\);/);
  assert.match(css, /@media \(max-width: 640px\) \{\s*\.catalogue-filter-grid, \.catalogue-row \{ grid-template-columns: minmax\(0, 1fr\);/);
});

// Exercise real page/hook logic with controlled React, router, timers and API boundaries.
function pageHarness(path, extra = {}) {
  const slots = []; let cursor = 0; let effects = []; const requests = []; const navigations = [];
  let query = extra.query || "";
  const equal = (a, b) => a && b && a.length === b.length && a.every((value, i) => Object.is(value, b[i]));
  const hooks = {
    useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = initial; return [slots[i], (value) => { slots[i] = typeof value === "function" ? value(slots[i]) : value; }]; },
    useRef(initial) { const i = cursor++; return slots[i] ||= { current: initial }; },
    useMemo(fn, deps) { const i = cursor++; if (!slots[i] || !equal(slots[i].deps, deps)) slots[i] = { value: fn(), deps }; return slots[i].value; },
    useCallback(fn, deps) { return hooks.useMemo(() => fn, deps); },
    useEffect(fn, deps) { const i = cursor++; if (!slots[i] || !equal(slots[i].deps, deps)) { const old = slots[i]; slots[i] = { deps }; effects.push(() => { old?.cleanup?.(); slots[i].cleanup = fn(); }); } },
  };
  const controls = component("../components/catalogue-filters.js", { react: hooks, "./filter-toolbar": component("../components/filter-toolbar.js", {}) });
  const workspace = { customerId: "customer", siteId: "site", reloadKey: "1", sites: [], customers: [] };
  const navigate = (method, href) => { navigations.push({ method, href }); query = href.split("?")[1] || ""; };
  const router = { push: (href) => navigate("push", href), replace: (href) => navigate("replace", href) };
  const Page = component(path, {
    react: hooks,
    "next/link": { __esModule: true, default: "a" },
    "next/navigation": { useRouter: () => router, useSearchParams: () => new URLSearchParams(query) },
    "../../components/access-denied": { AccessDenied: "denied" },
    "../../components/auth-context": { useAuth: () => ({ hasPermission: () => true, hasPermissionInContext: () => true }) },
    "../../components/workspace-context": { useWorkspaceContext: () => workspace },
    "../../components/page-header": { PageHeader: "header" },
    "../../components/entity-catalogue": catalogue,
    "../../components/catalogue-filters": controls,
    "../../lib/record-context.mjs": { recordContextOptions: () => ({}) },
    "../../lib/api": { apiRequest: async (url) => { requests.push(url); return extra.response ? extra.response(url) : []; } },
    ...extra.imports,
  }).default;
  const renderPage = () => { cursor = 0; const tree = Page(); const pending = effects; effects = []; pending.forEach((effect) => effect()); return tree; };
  function find(node, predicate) {
    if (!node || typeof node !== "object") return null;
    if (Array.isArray(node)) return node.map((child) => find(child, predicate)).find(Boolean);
    if (predicate(node)) return node;
    return find(node.props?.children, predicate);
  }
  const filters = () => find(renderPage(), (node) => node.type === controls.CatalogueFilters);
  return { render: renderPage, find, requests, navigations, workspace, filters,
    controls: () => controls.CatalogueFilters(filters().props),
    catalogue: () => find(renderPage(), (node) => node.type === catalogue.EntityCatalogue),
    navigate(queryString) { query = queryString; renderPage(); },
    unmount() { slots.forEach((slot) => slot?.cleanup?.()); },
  };
}
const settle = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
const serviceFilters = await import("../lib/service-list-filters.mjs");
const serviceHarness = (extra = {}) => pageHarness("../app/services/page.js", { ...extra, imports: { "../../lib/service-list-filters.mjs": serviceFilters } });

test("Both catalogues debounce typing, cancel superseded text, and expose no Apply action", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  for (const harness of [serviceHarness(), pageHarness("../app/business-functions/page.js")]) {
    harness.render(); await settle();
    const initialRequests = harness.requests.length;
    harness.filters().props.search.change(" d ");
    t.mock.timers.tick(200);
    harness.filters().props.search.change(" dns ");
    t.mock.timers.tick(299); harness.render(); await settle();
    assert.equal(harness.requests.length, initialRequests);
    t.mock.timers.tick(1); harness.render(); await settle();
    assert.ok(harness.requests.some((url) => url.includes("search=dns")));
    const html = renderToStaticMarkup(harness.controls());
    assert.doesNotMatch(html, /Apply search/);
    assert.match(html, /type="search"/);
    assert.match(html, /Search (services|business functions)\.\.\./);
    harness.unmount();
  }
});

test("Service selects apply immediately, count criteria, and preserve bookmarked/back navigation", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const harness = serviceHarness({ query: "search=dns&service_type_id=type-1&archived=true" });
  harness.render(); await settle();
  assert.equal(harness.filters().props.activeCount, 2);
  const primary = harness.filters().props.primary;
  harness.find(primary, (node) => node.type === "select").props.onChange({ target: { value: "type-2" } });
  harness.render(); await settle();
  assert.deepEqual(harness.navigations.at(-1), { method: "push", href: "/services?search=dns&service_type_id=type-2&archived=true" });
  assert.ok(harness.requests.some((url) => url.includes("service_type_id=type-2") && url.includes("archived=true")));
  harness.filters().props.search.change("storage"); t.mock.timers.tick(300); harness.render(); await settle();
  assert.equal(harness.navigations.at(-1).method, "replace");
  harness.filters().props.search.change("pending");
  harness.navigate("search=dns&service_type_id=type-1&archived=true");
  assert.equal(harness.filters().props.search.draft, "dns");
  t.mock.timers.tick(300);
  assert.ok(!harness.navigations.at(-1).href.includes("pending"));
  harness.unmount();
});

test("Clear is contextual, resets every criterion, and cancels pending searches on both pages", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  for (const harness of [serviceHarness(), pageHarness("../app/business-functions/page.js")]) {
    harness.render(); await settle();
    assert.doesNotMatch(renderToStaticMarkup(harness.controls()), /Clear filters/);
    harness.filters().props.search.change("pending");
    assert.match(renderToStaticMarkup(harness.controls()), /Clear filters/);
    const checkbox = harness.find(harness.filters().props.children, (node) => node.type === "input" && node.props.type === "checkbox");
    checkbox.props.onChange({ target: { checked: true } });
    harness.render(); await settle();
    assert.equal(harness.filters().props.activeCount, 1);
    harness.filters().props.onClear(); harness.render(); await settle();
    t.mock.timers.tick(500); harness.render(); await settle();
    assert.equal(harness.filters().props.search.draft, "");
    assert.equal(harness.filters().props.activeCount, 0);
    assert.doesNotMatch(renderToStaticMarkup(harness.controls()), /Clear filters/);
    harness.unmount();
  }
});

test("Quick filters keep their semantics, count actual criteria and use native accessible controls", async () => {
  const harness = serviceHarness({ response: (url) => url === "/services/summary" ? { total: 10, critical: 4 } : url === "/criticality-levels" ? [{ id: "critical-id", key: "critical", name: "Critical" }] : [] });
  harness.render(); await settle();
  const button = (text) => harness.find(harness.controls(), (node) => node.type === "button" && node.props.children?.[0]?.props?.children === text);
  button("Critical").props.onClick(); harness.render(); await settle();
  button("Missing owner").props.onClick(); harness.render(); await settle();
  assert.equal(harness.filters().props.activeCount, 2);
  assert.equal(button("Critical").props["aria-pressed"], true);
  assert.equal(button("Missing owner").props["aria-pressed"], true);
  for (const [label, attention] of [["Missing dependencies", "missing_dependencies"], ["Missing recovery", "missing_recovery_targets"], ["Incomplete", "incomplete"]]) {
    button(label).props.onClick(); harness.render(); await settle();
    assert.ok(harness.navigations.at(-1).href.includes(`attention=${attention}`));
    assert.equal(harness.filters().props.activeCount, 2);
  }
  const html = renderToStaticMarkup(harness.controls());
  assert.match(html, /<details class="catalogue-more-filters"><summary>Filters \(2\)<\/summary>/);
  assert.doesNotMatch(html, /tabindex="-1"|onkeydown/);
  // Native details/summary provides Enter/Space toggling and expanded state without controlled reopening.
  assert.equal(harness.find(harness.controls(), (node) => node.type === "details").props.open, undefined);
  button("All").props.onClick(); harness.render(); await settle();
  assert.equal(harness.filters().props.activeCount, 0);
  harness.unmount();
});

test("Business Functions includes archived immediately and searches existing fields", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const records = [{ id: "active", name: "Connectivity", active: true }, { id: "old", name: "Retired", active: false }];
  const harness = pageHarness("../app/business-functions/page.js", { response(url) {
    if (!url.startsWith("/business-functions?")) return [];
    const query = new URL(url, "https://atlas.test").searchParams;
    return records.filter((item) => (query.get("active_only") !== "true" || item.active) && item.name.toLowerCase().includes(query.get("search")));
  } });
  harness.render(); await settle();
  assert.deepEqual(harness.catalogue().props.children.map((node) => node.props.item.id), ["active"]);
  harness.find(harness.controls(), (node) => node.type === "input" && node.props.type === "checkbox").props.onChange({ target: { checked: true } });
  harness.render(); await settle();
  assert.deepEqual(harness.catalogue().props.children.map((node) => node.props.item.id), ["active", "old"]);
  harness.filters().props.search.change(" retired "); t.mock.timers.tick(300); harness.render(); await settle();
  assert.deepEqual(harness.catalogue().props.children.map((node) => node.props.item.id), ["old"]);
  harness.unmount();
});

test("Both pages retain results while loading and reject stale successes and failures", async () => {
  for (const make of [serviceHarness, (extra) => pageHarness("../app/business-functions/page.js", extra)]) {
    const pending = [];
    const harness = make({ response(url) {
      if (url.startsWith(make === serviceHarness ? "/services?" : "/business-functions?")) return new Promise((resolve, reject) => pending.push({ resolve, reject }));
      return [];
    } });
    harness.render(); pending.shift().resolve([{ id: "initial" }]); await settle();
    const first = harness.catalogue().props.onRefresh();
    const old = pending.shift();
    assert.equal(harness.catalogue().props.loading, true);
    assert.equal(harness.catalogue().props.count, 1);
    const second = harness.catalogue().props.onRefresh(); pending.shift().resolve([{ id: "latest" }]); await second;
    old.resolve([{ id: "stale" }]); await first;
    const row = harness.catalogue().props.children[0];
    assert.equal((row.props.service || row.props.item).id, "latest");
    const third = harness.catalogue().props.onRefresh(); const staleError = pending.shift();
    const fourth = harness.catalogue().props.onRefresh(); pending.shift().resolve([{ id: "newest" }]); await fourth;
    staleError.reject(new Error("Old failure")); await third;
    assert.equal(harness.catalogue().props.error, "");
    assert.equal(harness.catalogue().props.loading, false);
    harness.workspace.reloadKey = "2"; harness.render();
    assert.equal(harness.catalogue().props.count, 0);
    harness.unmount(); pending.shift().resolve([{ id: "unmounted" }]); await settle();
  }
});

test("Retained catalogue rows stay visible during loading or refresh errors without flashing empty state", () => {
  for (const state of [{ loading: true }, { error: "Failed" }]) {
    const html = render("EntityCatalogue", { label: "Services", count: 1, empty: "No matches", children: React.createElement("li", null, "Retained row"), ...state });
    assert.match(html, /Retained row/); assert.doesNotMatch(html, /No matches/);
  }
});
