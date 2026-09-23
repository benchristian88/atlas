import test from "node:test";
import assert from "node:assert/strict";
import { compareIp, sortNetworkMembers } from "../lib/network-sort.mjs";
import { auditDetails } from "../lib/audit-details.mjs";
import { CATEGORY_PREVIEW_COUNT } from "../lib/infrastructure-topology.mjs";
test("category previews at boundaries", () => {
  for (const [count, shown, hidden] of [[5,5,0], [12,12,0], [17,12,5]]) {
    assert.equal(Math.min(count, CATEGORY_PREVIEW_COUNT), shown);
    assert.equal(Math.max(0, count - CATEGORY_PREVIEW_COUNT), hidden);
  }
});
test("numeric IPv4 and compressed/mapped IPv6 sorting", () => {
  assert.deepEqual([100,20,9,2].map(n => `10.0.0.${n}`).sort(compareIp), [2,9,20,100].map(n => `10.0.0.${n}`));
  assert.ok(compareIp("2001:db8::9", "2001:db8::10") < 0);
  assert.equal(compareIp("::ffff:192.0.2.1", "0:0:0:0:0:ffff:c000:201"), 0);
  assert.ok(compareIp("10.0.0.1", null) < 0);
});
test("network sorting preserves deterministic secondary order in both directions", () => {
  const assets = {a:{name:"Alpha"}, b:{name:"Beta"}};
  const members = [{id:"2",asset_id:"b",ip_address:"10.0.0.2"}, {id:"1",asset_id:"a",ip_address:"10.0.0.2"}];
  for (const direction of [-1,1]) assert.equal(sortNetworkMembers(members,assets,{key:"ip_address", direction})[0].id,"1");
  assert.equal(sortNetworkMembers(members,assets,{key:"asset", direction:-1})[0].id,"2");
});
test("audit nested differences preserve missing and null values and redact secrets", () => {
  const result = auditDetails({name:{from:"Old",to:"New"}, added:{after:null}, removed:{before:false}, nested:{password:{from:"private",to:"secret"}}, changed_fields:["name"], snapshot:{to:{api_token:"never show"}}});
  assert.equal(result.changes[1].hasBefore,false);
  assert.equal(result.changes[1].after,null);
  assert.equal(result.changes[2].hasAfter,false);
  assert.ok(!JSON.stringify(result).includes("never show"));
  assert.ok(!JSON.stringify(result).includes("private"));
  assert.equal(result.facts[0].value,"[redacted]");
});

test("snapshot diffs show nested fields and omit unchanged values", () => {
  const { changes } = auditDetails({before:{name:"Old",nested:{keep:true,removed:1}},after:{name:"New",nested:{keep:true,added:2}}});
  assert.deepEqual(changes.map(row => row.field), ["name", "nested / removed", "nested / added"]);
});
