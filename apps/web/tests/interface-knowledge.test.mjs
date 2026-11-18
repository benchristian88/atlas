import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFile } from "node:fs/promises";
import { loadComponent } from "./helpers/components.mjs";

const { InterfaceAttachment, InterfaceDiscoveryDetails } = loadComponent(new URL("../components/interface-knowledge.js", import.meta.url));
const fact = { predicate: "proxmox.vlan_tag", value: 22, source_name: "Proxmox lab",
  last_observed_at: "2026-11-01T00:00:00Z", is_accepted: true, accepted_at: "2026-11-01T01:00:00Z" };
const render = item => renderToStaticMarkup(React.createElement(InterfaceAttachment, { item }));
const renderDetails = facts => renderToStaticMarkup(React.createElement(InterfaceDiscoveryDetails, { facts }));

test("accepted VLAN and bridge observations do not invent an assignment", () => {
  const html = render({ assigned_network: null, observed_facts: [{ ...fact, value: 5 }, { ...fact, predicate: "proxmox.bridge_name", value: "vmbr0" }] });
  assert.match(html, /<dt>Assigned Atlas Network<\/dt><dd>Not assigned<\/dd>/);
  assert.match(html, /<dt>Observed Proxmox attachment<\/dt><dd><code>vmbr0<\/code> · VLAN tag 5<\/dd>/);
  assert.doesNotMatch(html, /Proxmox lab|Last observed|Accepted/);
  assert.match(render({}), /<dt>Observed attachment<\/dt><dd>Not recorded<\/dd>/);
  assert.equal(renderDetails([]), "");
});

test("canonical and differing observed VLANs remain distinct; zero VLAN is visible", () => {
  const html = render({ assigned_network: { name: "Curated LAN", vlan_id: 9 }, observed_facts: [fact] });
  assert.match(html, /Assigned Atlas Network<\/dt><dd>Curated LAN · VLAN 9/);
  assert.match(html, /Observed Proxmox attachment<\/dt><dd>VLAN tag 22/);
  assert.match(render({ assigned_network: { name: "Native", vlan_id: 0 }, observed_facts: [{ ...fact, value: 0 }] }), /Native · VLAN 0.*VLAN tag 0/);
});

test("accepted older evidence and newer unaccepted evidence retain individual dates and states", () => {
  const facts = [fact, { ...fact, value: 33, is_accepted: false, accepted_at: null,
    source_name: null, last_observed_at: "2026-11-02T00:00:00Z" }];
  assert.match(render({ observed_facts: facts }), /VLAN tag 33/);
  const html = renderDetails(facts);
  assert.match(html, /^<details class="[^"]+"><summary>Discovery details<\/summary>/);
  assert.match(html, /<code>22<\/code>.*>Accepted<.*<code>33<\/code>.*>Not accepted</);
  assert.match(html, /Source unavailable/);
  assert.match(html, /dateTime="2026-11-01T00:00:00Z"/);
  assert.match(html, /dateTime="2026-11-01T01:00:00Z"/);
  assert.match(html, /dateTime="2026-11-02T00:00:00Z"/);
  assert.equal((html.match(/Last observed/g) || []).length, 2);
  assert.doesNotMatch(html, /withdrawn|Confirmed current/);
});

test("Asset detail requests one batched projection and renders backend membership", async () => {
  const page = await readFile(new URL("../app/assets/[id]/page.js", import.meta.url), "utf8");
  const card = await readFile(new URL("../components/asset-networking.js", import.meta.url), "utf8");
  assert.match(page, /asset-interfaces\?asset_id=\$\{id\}&include_knowledge=true/);
  assert.match(card, /<InterfaceAttachment .*item=\{item\}/);
  assert.doesNotMatch(page + card, /assertions\?subject_type=asset_interface|networksById\[item.network_id\]/);
});
