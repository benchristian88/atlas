import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFile } from "node:fs/promises";
import { loadComponent } from "./helpers/components.mjs";

const { InterfaceKnowledge } = loadComponent(new URL("../components/interface-knowledge.js", import.meta.url));
const fact = { predicate: "proxmox.vlan_tag", value: 22, source_name: "Proxmox lab",
  last_observed_at: "2026-11-01T00:00:00Z", is_accepted: true, accepted_at: "2026-11-01T01:00:00Z" };
const render = item => renderToStaticMarkup(React.createElement(InterfaceKnowledge, { item }));

test("accepted VLAN and bridge observations do not invent an assignment", () => {
  const html = render({ assigned_network: null, observed_facts: [fact, { ...fact, predicate: "proxmox.bridge_name", value: "vmbr0" }] });
  for (const text of ["No Network assigned", "Observed VLAN", "22", "Observed bridge", "vmbr0", "Proxmox lab", "Last observed", ">Accepted<"])
    assert.ok(html.includes(text), text);
  assert.match(html, /dateTime="2026-11-01T00:00:00Z"/);
  assert.match(html, /do not assign a Network or confirm the current configuration/);
  assert.doesNotMatch(html, /Canonical VLAN|Current from source/);
});

test("canonical and differing observed VLANs remain distinct; zero VLAN is visible", () => {
  const html = render({ assigned_network: { name: "Curated LAN", vlan_id: 9 }, observed_facts: [fact] });
  assert.match(html, /Assigned Network: Curated LAN · Canonical VLAN 9/);
  assert.match(html, /Observed VLAN.*22/);
  assert.match(render({ assigned_network: { name: "Native", vlan_id: 0 } }), /Canonical VLAN 0/);
});

test("accepted older evidence and newer unaccepted evidence retain individual dates and states", () => {
  const html = render({ observed_facts: [fact, { ...fact, value: 33, is_accepted: false, accepted_at: null,
    source_name: null, last_observed_at: "2026-11-02T00:00:00Z" }] });
  assert.match(html, />Accepted</); assert.match(html, />Not accepted</);
  assert.match(html, /Source unavailable/);
  assert.match(html, /dateTime="2026-11-01T00:00:00Z"/); assert.match(html, /dateTime="2026-11-02T00:00:00Z"/);
  assert.equal((html.match(/Last observed/g) || []).length, 2);
  assert.doesNotMatch(html, /withdrawn|Confirmed current/);
});

test("Asset detail requests one batched projection and renders backend membership", async () => {
  const page = await readFile(new URL("../app/assets/[id]/page.js", import.meta.url), "utf8");
  assert.match(page, /asset-interfaces\?asset_id=\$\{id\}&include_knowledge=true/);
  assert.match(page, /<InterfaceKnowledge item=\{item\}/);
  assert.doesNotMatch(page, /assertions\?subject_type=asset_interface|networksById\[item.network_id\]/);
});
