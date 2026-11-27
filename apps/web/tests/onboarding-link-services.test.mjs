import assert from "node:assert/strict";
import { test } from "node:test";
import {
  MAPPING_SELECTION_LIMIT, mappingAssetContext, mappingPagePath, readUnconfirmedMapping, remainingMappingSelection,
  requiresMappingAcknowledgement, storeUnconfirmedMapping, submitMappingActions, toggleMappingAsset,
} from "../lib/onboarding-link-services.mjs";

const assets = ["Alpha", "Beta", "Gamma", "Delta"].map(name => ({ id: name.toLowerCase(), name }));

test("picker pages encode only the explicit filters and bound their results", () => {
  const path = "/onboarding/customer/site/link-services/services/service";
  const url = new URL(mappingPagePath(path, { search: "NAS & backup", asset_type: "physical_server", offset: 25 }), "http://atlas");
  assert.equal(url.pathname, path);
  assert.deepEqual(Object.fromEntries(url.searchParams), {
    limit: "25", search: "NAS & backup", asset_type: "physical_server", offset: "25",
  });
  assert.equal(mappingPagePath(path, { search: "", offset: 0 }), path + "?limit=25");
});

test("selection toggles exact Assets and bounds the number of writes per confirmation", () => {
  const all = Array.from({ length: MAPPING_SELECTION_LIMIT + 2 }, (_, index) => ({
    id: String(index), name: `Asset ${index}`, type_name: "Virtual Machine", site_id: "site",
    hostname: "shared.lab",
  }));
  const selected = all.reduce(toggleMappingAsset, []);
  assert.equal(selected.length, MAPPING_SELECTION_LIMIT);
  assert.deepEqual(selected[0], {
    id: "0", name: "Asset 0", type_name: "Virtual Machine", hostname: "shared.lab",
  });
  assert.equal(toggleMappingAsset(selected, all[0]).length, MAPPING_SELECTION_LIMIT - 1);
});

test("independent writes distinguish committed, already linked, rejected and unconfirmed outcomes", async () => {
  const calls = [], markers = [];
  const request = async (path, options) => {
    calls.push([path, options.method]);
    if (path.endsWith("/alpha")) return { outcome: "added" };
    if (path.endsWith("/beta")) return { outcome: "already_exists" };
    if (path.endsWith("/gamma")) throw Object.assign(new Error("Retired"), { status: 409 });
    throw Object.assign(new Error("Connection lost"), { kind: "network" });
  };
  const selection = [...assets, { id: "echo", name: "Echo" }];
  const outcome = await submitMappingActions("/services/example", { kind: "add", assets: selection }, request, marker => markers.push(marker));
  assert.deepEqual(calls, assets.map(asset => [`/services/example/assets/${asset.id}`, "POST"]));
  assert.deepEqual(outcome.results.map(row => row.status), ["added", "already_exists", "rejected", "unconfirmed"]);
  assert.equal(outcome.results[2].reason, "Retired");
  assert.equal(outcome.unsubmitted, 1);
  assert.deepEqual(markers.slice(-2), [null, { kind: "add", id: "delta" }]);
  assert.deepEqual(remainingMappingSelection(selection, outcome.results, []), selection.slice(2));
  assert.deepEqual(remainingMappingSelection(selection, outcome.results, [{ asset: assets[3] }]), [assets[2], selection[4]]);
});

test("Asset identity always shows type and full UUID, with a hostname when available", () => {
  const first = {
    id: "12345678-0000-4000-8000-000000000001", name: "Provider", type_name: "Virtual Machine", hostname: "shared.lab",
  };
  const second = { ...first, id: "12345678-0000-4000-8000-000000000002" };
  assert.equal(mappingAssetContext(first), `Virtual Machine · shared.lab · ID ${first.id}`);
  assert.equal(mappingAssetContext(second), `Virtual Machine · shared.lab · ID ${second.id}`);
  for (const hostname of [null, "", undefined]) {
    assert.equal(mappingAssetContext({ ...first, hostname }), `Virtual Machine · ID ${first.id}`);
  }
  const selected = toggleMappingAsset(toggleMappingAsset([], first), second);
  assert.deepEqual(selected.map(mappingAssetContext), [mappingAssetContext(first), mappingAssetContext(second)]);
  assert.deepEqual(toggleMappingAsset(selected, first), [second]);
});

test("removal uses the confirmed relationship ID and version and permission errors stop further writes", async () => {
  const requests = [];
  const remove = await submitMappingActions("/services/one", {
    kind: "remove", mappingId: "relationship-a", removalVersion: "reviewed-version", assets: [assets[0]],
  }, async (...args) => requests.push(args), () => {});
  assert.deepEqual(requests, [["/services/one/mappings/relationship-a", {
    method: "DELETE", body: JSON.stringify({ removal_version: "reviewed-version" }),
  }]]);
  assert.equal(remove.results[0].status, "removed");
  const denied = await submitMappingActions("/services/two", { kind: "add", assets }, async () => {
    throw Object.assign(new Error("Permission revoked"), { status: 403 });
  }, () => {});
  assert.equal(denied.results.length, 1);
  assert.equal(denied.unsubmitted, 3);
});

test("unconfirmed operations retain only a single operation identity scoped to its Service", () => {
  const entries = new Map();
  globalThis.sessionStorage = {
    setItem: (key, value) => entries.set(key, value), getItem: key => entries.get(key),
    removeItem: key => entries.delete(key),
  };
  try {
    const marker = { id: "asset", kind: "add" };
    storeUnconfirmedMapping("actor:site:service1", marker);
    assert.deepEqual(readUnconfirmedMapping("actor:site:service1"), marker);
    assert.equal(readUnconfirmedMapping("actor:site:service2"), null);
    assert.equal(readUnconfirmedMapping("other:site:service1"), null);
    storeUnconfirmedMapping("actor:site:service1", null);
    assert.equal(readUnconfirmedMapping("actor:site:service1"), null);
  } finally {
    delete globalThis.sessionStorage;
  }
});

test("verified empty progress can continue and incomplete or restricted progress needs acknowledgement", () => {
  assert.equal(requiresMappingAcknowledgement({ linked: 0, unlinked: 0, mappings: 0, unavailable: 0 }), false);
  assert.equal(requiresMappingAcknowledgement({ linked: 2, unlinked: 1, mappings: 4, unavailable: 0 }), true);
  assert.equal(requiresMappingAcknowledgement({ linked: 2, unlinked: 0, mappings: 4, unavailable: 1 }), true);
  assert.equal(requiresMappingAcknowledgement(null), true);
});
