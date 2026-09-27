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
  assert.match(services, /update\(\{ search: searchDraft.trim\(\) \}\)/);
  assert.match(services, /update\(\{ serviceTypeId: event.target.value \}\)/);
  assert.match(functions, /\[showArchived, setShowArchived\] = useState\(false\)/);
  assert.match(functions, /active_only: String\(!showArchived\), search/);
  assert.match(functions, /setSearch\(searchDraft.trim\(\)\)/);
  assert.match(functions, /setShowArchived\(event.target.checked\)/);
  for (const page of [services, functions]) {
    assert.match(page, /hasPermissionInContext/); assert.match(page, /role="alert"/);
    assert.match(page, /<FilterToolbar/); assert.match(page, /<EntityCatalogue/); assert.doesNotMatch(page, /<table|<th>/);
  }
});
test("Catalogue focus and mobile layout use theme tokens", () => {
  const css = source("../app/globals.css");
  assert.match(css, /\.catalogue-row:focus-visible/);
  assert.match(css, /\.catalogue-health \.status-outage \{ background: var\(--danger\);/);
  assert.match(css, /@media \(max-width: 640px\) \{\s*\.catalogue-filter-grid, \.catalogue-row \{ grid-template-columns: minmax\(0, 1fr\);/);
});

// Run page event handlers and data loading with controlled auth/router/API boundaries.
function pageHarness(path, extra = {}) {
  const state = []; let cursor = 0; const requests = []; const navigations = [];
  const hooks = { useState(initial) { const index = cursor++; if (!(index in state)) state[index] = initial; return [state[index], (value) => { state[index] = typeof value === "function" ? value(state[index]) : value; }]; }, useCallback: (fn) => fn, useMemo: (fn) => fn(), useEffect() {} };
  const workspace = { customerId: "customer", siteId: "site", reloadKey: "1", sites: [], customers: [] };
  const Page = component(path, {
    react: hooks,
    "next/link": { __esModule: true, default: "a" },
    "next/navigation": { useRouter: () => ({ push: (href) => navigations.push(href) }), useSearchParams: () => new URLSearchParams("search=dns&service_type_id=type-1") },
    "../../components/access-denied": { AccessDenied: "denied" },
    "../../components/auth-context": { useAuth: () => ({ hasPermission: () => true, hasPermissionInContext: () => true }) },
    "../../components/workspace-context": { useWorkspaceContext: () => workspace },
    "../../components/page-header": { PageHeader: "header" },
    "../../components/entity-catalogue": catalogue,
    "../../components/filter-toolbar": { FilterToolbar: "toolbar" },
    "../../lib/record-context.mjs": { recordContextOptions: () => ({}) },
    "../../lib/api": { apiRequest: async (url) => { requests.push(url); return extra.response ? extra.response(url) : []; } },
    ...extra.imports,
  }).default;
  const renderPage = () => { cursor = 0; return Page(); };
  function find(node, predicate) {
    if (!node || typeof node !== "object") return null;
    if (Array.isArray(node)) return node.map((child) => find(child, predicate)).find(Boolean);
    if (predicate(node)) return node;
    return find(node.props?.children, predicate);
  }
  return { render: renderPage, find, requests, navigations };
}

test("Business Function search and archived controls request and display the intended records", async () => {
  const records = [{ id: "active", name: "Connectivity", description: "Home network", active: true, service_count: 1 }, { id: "old", name: "Old", description: "Retired network", active: false, service_count: 0 }];
  const harness = pageHarness("../app/business-functions/page.js", { response(url) {
    if (!url.startsWith("/business-functions?")) return [];
    const query = new URL(url, "https://atlas.test").searchParams;
    return records.filter((item) => (query.get("active_only") !== "true" || item.active) && `${item.name} ${item.description}`.toLowerCase().includes(query.get("search").toLowerCase()));
  } });
  const catalogueNode = () => harness.find(harness.render(), (node) => node.type === catalogue.EntityCatalogue);
  await catalogueNode().props.onRefresh();
  assert.deepEqual(catalogueNode().props.children.map((node) => node.props.item.id), ["active"]);
  harness.find(harness.render(), (node) => node.type === "input" && node.props.type === "checkbox").props.onChange({ target: { checked: true } });
  await catalogueNode().props.onRefresh();
  assert.deepEqual(catalogueNode().props.children.map((node) => node.props.item.id), ["active", "old"]);
  harness.find(harness.render(), (node) => node.type === "input" && node.props.placeholder).props.onChange({ target: { value: " retired " } });
  harness.find(harness.render(), (node) => node.type === "toolbar").props.onSubmit({ preventDefault() {} });
  await catalogueNode().props.onRefresh();
  assert.deepEqual(catalogueNode().props.children.map((node) => node.props.item.id), ["old"]);
  assert.ok(harness.requests.includes("/business-functions?active_only=false&search=retired"));
});

test("Service search and type controls navigate with filter state and load the existing API", async () => {
  const filters = await import("../lib/service-list-filters.mjs");
  const harness = pageHarness("../app/services/page.js", { imports: { "../../lib/service-list-filters.mjs": filters } });
  harness.find(harness.render(), (node) => node.type === "input" && node.props.placeholder).props.onChange({ target: { value: " storage " } });
  harness.find(harness.render(), (node) => node.type === "toolbar").props.onSubmit({ preventDefault() {} });
  assert.equal(harness.navigations.at(-1), "/services?search=storage&service_type_id=type-1");
  harness.find(harness.render(), (node) => node.type === "select" && node.props.value === "type-1").props.onChange({ target: { value: "type-2" } });
  assert.equal(harness.navigations.at(-1), "/services?search=dns&service_type_id=type-2");
  await harness.find(harness.render(), (node) => node.type === catalogue.EntityCatalogue).props.onRefresh();
  assert.ok(harness.requests.includes("/services?search=dns&service_type_id=type-1"));
});
