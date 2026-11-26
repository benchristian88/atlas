import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  beginPendingApply, changeSelection, clearPendingApply, creationAllowed, editEntry, entryDefaults, orderedDefinitions,
  pendingApplyKey, readPendingApply, recommendedState, restrictedClassifications, selectionPayload, selectionState,
  validateCapabilities, validApplyOutcome,
} from "../lib/onboarding-capabilities.mjs";

const catalogue = JSON.parse(readFileSync(new URL("../../api/app/onboarding_data/homelab-v1.json", import.meta.url)));
const { catalogue_id, schema_version, content_version } = catalogue;
const empty = { catalogue_id, schema_version, content_version, functions: [], services: [], associations: [] };
const allFunctions = catalogue.functions;
const allServices = allFunctions.flatMap(({ services }) => services);
const serviceKeys = Object.fromEntries(allServices.map(({ service_type_name }) =>
  [service_type_name, `${service_type_name.toLowerCase()}_service`]));
const permissions = {
  can_manage: true, can_create_functions: true, can_create_services: true,
  can_create_associations: true, can_view_service_types: true, can_view_criticality_levels: true,
};
const data = {
  profile: "homelab", version: 2, permissions, catalogue, draft: null, draft_stale: false,
  default_service_type_keys: serviceKeys, default_criticality_key: "medium",
  defaults: {
    ...empty,
    functions: allFunctions.filter(({ preselected }) => preselected).map(({ id }) => ({ id })),
    services: allServices.filter(({ preselected }) => preselected).map(({ id }) => ({ id })),
    associations: catalogue.associations.filter(({ service_id }) => allServices.find(({ id }) => id === service_id).preselected)
      .map(({ id }) => id),
  },
};
const [group, other] = allFunctions;
const standard = group.services.find(({ selection_tier }) => selection_tier === "standard");
const extended = group.services.find(({ selection_tier }) => selection_tier === "extended");
const linkFor = (service) => catalogue.associations.find(({ service_id }) => service_id === service.id).id;

test("first Homelab visit consumes server defaults and later entry can start empty", () => {
  const status = validateCapabilities(data, "homelab");
  assert.deepEqual(selectionPayload(status, selectionState(status)), data.defaults);
  assert.deepEqual([data.defaults.functions.length, data.defaults.services.length, data.defaults.associations.length], [8, 24, 24]);
  const later = { ...data, defaults: empty };
  assert.deepEqual(selectionPayload(later, selectionState(later)), empty);
  assert.deepEqual(selectionPayload(later, recommendedState(later)), data.defaults);
});

test("valid saved draft takes precedence, and stale definitions never populate the selection", () => {
  const draft = { ...empty, functions: [{ id: group.id, name: "Ngā hononga" }] };
  const status = { ...data, draft };
  assert.deepEqual(selectionPayload(status, selectionState(status)), draft);
  const stale = { ...status, draft_stale: true, draft: { ...draft, content_version: "0.0.1" } };
  assert.deepEqual(selectionPayload(stale, selectionState(stale)), data.defaults);
  assert.throws(() => validateCapabilities({ ...stale, draft_stale: false }, "homelab"), /invalid Capabilities/);
});

test("a Service-only API draft round trips with its description and classification", () => {
  const draft = {
    ...empty,
    services: [{ id: standard.id, description: "Customer-edited Service description",
      criticality_key: data.default_criticality_key }],
  };
  const status = validateCapabilities({ ...data, draft }, "homelab");
  assert.deepEqual(selectionPayload(status, selectionState(status)), draft);
});

test("a saved Function and Service round trip without an unselected Supports association", () => {
  const draft = { ...empty, functions: [{ id: group.id }], services: [{ id: standard.id }] };
  const status = validateCapabilities({ ...data, draft }, "homelab");
  assert.deepEqual(selectionPayload(status, selectionState(status)), draft);
});

test("editing overrides and unrelated selections leaves saved association choices alone", () => {
  const draft = {
    ...empty,
    functions: [{ id: other.id }, { id: group.id }],
    services: [{ id: extended.id }, { id: standard.id, name: standard.name, description: null }],
    associations: [linkFor(extended)],
  };
  const status = { ...data, draft };
  let state = selectionState(status);
  assert.deepEqual(selectionPayload(status, state), draft);
  state = editEntry(state, data, standard, { ...entryDefaults(data, standard), description: "Edited description" });
  state = editEntry(state, data, other, { name: "Unrelated Function" });
  const edited = {
    ...draft,
    functions: [{ id: other.id, name: "Unrelated Function" }, { id: group.id }],
    services: [{ id: extended.id }, { id: standard.id, name: standard.name, description: "Edited description" }],
  };
  assert.deepEqual(selectionPayload(status, state), edited);

  const unrelated = other.services[0];
  state = changeSelection(state, catalogue, other, { service: unrelated, selected: true });
  assert.deepEqual(selectionPayload(status, state).associations, [linkFor(extended), linkFor(unrelated)]);
  state = changeSelection(state, catalogue, other, { service: unrelated, selected: false });
  assert.deepEqual(selectionPayload(status, state), edited);

  state = changeSelection(state, catalogue, group, { selected: false });
  state = changeSelection(state, catalogue, group, { selected: true });
  const restored = selectionPayload(status, state);
  assert.deepEqual(new Set(restored.services), new Set(edited.services));
  assert.deepEqual(restored.associations, [linkFor(extended)]);
});

test("deliberately reselecting an API-saved Service adds its parent and Supports link", () => {
  let state = selectionState(data, { ...empty, services: [{ id: standard.id }] });
  state = changeSelection(state, catalogue, group, { service: standard, selected: false });
  state = changeSelection(state, catalogue, group, { service: standard, selected: true });
  assert.deepEqual(selectionPayload(data, state), {
    ...empty, functions: [{ id: group.id }], services: [{ id: standard.id }], associations: [linkFor(standard)],
  });
});

test("group deselection removes associations and group reselection restores only remembered Services", () => {
  let state = selectionState(data);
  state = changeSelection(state, catalogue, group, { service: standard, selected: false });
  state = changeSelection(state, catalogue, group, { service: extended, selected: true });
  const before = selectionPayload(data, state);
  state = changeSelection(state, catalogue, group, { selected: false });
  const deselected = selectionPayload(data, state);
  assert.equal(deselected.functions.some(({ id }) => id === group.id), false);
  assert.equal(deselected.services.some(({ id }) => group.services.some((service) => service.id === id)), false);
  assert.equal(deselected.associations.some((id) => catalogue.associations.some((link) => link.id === id && link.business_function_id === group.id)), false);
  state = changeSelection(state, catalogue, group, { selected: true });
  const restored = selectionPayload(data, state);
  assert.deepEqual(new Set(restored.functions), new Set(before.functions));
  assert.deepEqual(new Set(restored.services), new Set(before.services));
  assert.deepEqual(new Set(restored.associations), new Set(before.associations));
});

test("a Function can be selected alone and selecting a Service activates its parent", () => {
  let state = selectionState(data, empty);
  state = changeSelection(state, catalogue, other, { selected: true });
  assert.deepEqual(selectionPayload(data, state), { ...empty, functions: [{ id: other.id }] });
  state = changeSelection(state, catalogue, group, { service: extended, selected: true });
  const payload = selectionPayload(data, state);
  assert.deepEqual(payload.functions, [{ id: other.id }, { id: group.id }]);
  assert.deepEqual(payload.services, [{ id: extended.id }]);
  assert.deepEqual(payload.associations, [catalogue.associations.find(({ service_id }) => service_id === extended.id).id]);
  state = changeSelection(state, catalogue, group, { service: extended, selected: false });
  assert.deepEqual(selectionPayload(data, state), { ...empty, functions: payload.functions });
});

test("Select all includes both tiers and associations remain unique and tied to authoritative endpoints", () => {
  let state = selectionState(data, {
    ...empty,
    functions: [{ id: group.id }, { id: "bf.invalid" }, { id: group.id }],
    services: [{ id: "svc.invalid" }, { id: other.services[0].id }, { id: standard.id }, { id: standard.id }],
    associations: ["assoc.invalid", linkFor(other.services[0]), linkFor(standard), linkFor(standard)],
  });
  assert.deepEqual(selectionPayload(data, state).services, [{ id: other.services[0].id }, { id: standard.id }]);
  assert.deepEqual(selectionPayload(data, state).associations, [linkFor(standard)]);
  state = changeSelection(state, catalogue, group, { selected: true, all: true });
  const payload = selectionPayload(data, state);
  assert.deepEqual(payload.services.map(({ id }) => id), [other.services[0].id, ...group.services.map(({ id }) => id)]);
  assert.deepEqual(payload.associations, catalogue.associations.filter(({ business_function_id }) => business_function_id === group.id)
    .map(({ id }) => id));
  const reordered = { ...data, catalogue: { ...catalogue, functions: [...allFunctions].reverse() } };
  assert.deepEqual(selectionPayload(reordered, state), payload);
  assert.deepEqual(orderedDefinitions(reordered.catalogue.functions), allFunctions);
});

test("overrides retain stable IDs, preserve Unicode, support null descriptions and reset per entry", () => {
  let state = selectionState(data);
  state = editEntry(state, data, group, { name: "Tāmaki 家庭", description: null, service_type_key: "ignored" });
  state = editEntry(state, data, standard, { ...entryDefaults(data, standard), criticality_key: "high", id: "ignore" });
  const before = selectionPayload(data, state);
  assert.deepEqual(before.functions[0], { id: group.id, name: "Tāmaki 家庭", description: null });
  assert.deepEqual(before.services.find(({ id }) => id === standard.id), { id: standard.id, criticality_key: "high" });
  state = editEntry(state, data, group, {});
  assert.deepEqual(selectionPayload(data, state), { ...before, functions: data.defaults.functions });
  assert.deepEqual(selectionPayload(data, recommendedState(data)), data.defaults);
  assert.equal(catalogue.functions[0].name, group.name);
});

test("Blank has no starter catalogue and invalid payloads fail closed", () => {
  const blank = { ...data, profile: "blank", catalogue: null, defaults: null };
  assert.equal(selectionState(validateCapabilities(blank, "blank")).functions.size, 0);
  assert.throws(() => validateCapabilities(data, "blank"), /invalid Capabilities/);
  assert.throws(() => validateCapabilities({ ...data, catalogue: { ...catalogue, associations: [null] } }, "homelab"), /invalid Capabilities/);
  assert.throws(() => validateCapabilities({ ...data, permissions: {} }, "homelab"), /invalid Capabilities/);
});

test("creation needs Site management and each selected Customer-wide grant", () => {
  const functionOnly = { ...empty, functions: [{ id: group.id }] };
  assert.equal(creationAllowed(permissions, data.defaults), true);
  for (const key of ["can_manage", "can_create_functions", "can_create_services", "can_create_associations"]) {
    assert.equal(creationAllowed({ ...permissions, [key]: false }, data.defaults), false, key);
  }
  assert.equal(creationAllowed({ ...permissions, can_create_associations: false, can_create_services: false }, functionOnly), true);
});

test("a shared draft with a now-restricted classification can be corrected by restoring its default", () => {
  const restricted = { ...data, permissions: { ...permissions, can_view_service_types: false } };
  const state = editEntry(selectionState(data), data, standard, { service_type_key: "alternate_type" });
  assert.deepEqual([...restrictedClassifications(restricted, selectionPayload(data, state))], [standard.id]);
  const restored = editEntry(state, data, standard, {});
  assert.equal(restrictedClassifications(restricted, selectionPayload(data, restored)).size, 0);
  const explicit = { ...empty, services: [{ id: standard.id, service_type_key: serviceKeys[standard.service_type_name] }] };
  assert.deepEqual(selectionPayload(data, selectionState(data, explicit)), explicit);
  assert.equal(restrictedClassifications(restricted, explicit).size, 0);
});

test("an Apply retry or remount uses the original UUID and version, scoped to the account and pair", () => {
  const entries = new Map();
  globalThis.window = { crypto: webcrypto, sessionStorage: {
    setItem: (key, value) => entries.set(key, value),
    getItem: (key) => entries.get(key) ?? null,
    removeItem: (key) => entries.delete(key),
  } };
  try {
    const key = pendingApplyKey("user", "/onboarding/customer/site");
    const apply = beginPendingApply(key, 5);
    assert.deepEqual(Object.keys(JSON.parse(entries.get(key))), ["version", "submission_id"]);
    assert.deepEqual(readPendingApply(key), apply);
    assert.deepEqual(beginPendingApply(key, 6), apply);
    assert.equal(readPendingApply(pendingApplyKey("other", "/onboarding/customer/site")), null);
    assert.equal(readPendingApply(pendingApplyKey("user", "/onboarding/customer/other")), null);
    const receipt = { ...apply, version: 6, current_stage: "integrations", created: { functions: 1, services: 1, associations: 1 } };
    assert.equal(validApplyOutcome(receipt, apply), true);
    assert.equal(validApplyOutcome({ ...receipt, version: 5 }, apply), false);
    clearPendingApply(key);
    assert.notEqual(beginPendingApply(key, 7).submission_id, apply.submission_id);
  } finally {
    delete globalThis.window;
  }
});
