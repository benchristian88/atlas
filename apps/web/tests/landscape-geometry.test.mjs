import test from "node:test";
import assert from "node:assert/strict";
import { landscapeGeometry, fitLandscape } from "../lib/landscape-geometry.mjs";

test("lane geometry uses width and keeps native readable node dimensions", () => {
  for (const width of [760, 1040, 1400]) {
    for (const expanded of [false, true]) {
      const layout = landscapeGeometry(width, expanded);
      assert.equal(layout.width, Math.max(width - 32, 3 * ((expanded ? 224 : 200) + 24)));
      assert.ok(layout.nodeWidth >= (expanded ? 224 : 200));
      assert.ok(layout.nodeWidth <= (expanded ? 264 : 226));
      assert.ok(layout.nodeWidth + 24 <= layout.stepX);
    }
  }
});
test("narrow viewports overflow instead of shrinking readable cards", () => {
  const layout = landscapeGeometry(320);
  assert.equal(layout.nodeWidth, 200);
  assert.ok(layout.width > 320);
});
test("expanded cards are modestly larger; inspector widths do not depend on height", () => {
  const embedded = landscapeGeometry(1040);
  const expanded = landscapeGeometry(1040, true);
  const hidden = landscapeGeometry(1400, true);
  assert.ok(expanded.nodeWidth > embedded.nodeWidth);
  assert.ok(expanded.nodeHeight > embedded.nodeHeight);
  assert.equal(expanded.nodeWidth, hidden.nodeWidth);
  assert.ok(hidden.stepX > expanded.stepX);
});
test("explicit Fit alone contains tall graphs in both dimensions", () => {
  const layout = landscapeGeometry(1040, true);
  for (const height of [300, 1240, 2400]) {
    const scale = fitLandscape(1040, 680, layout.width, height);
    assert.ok(layout.width * scale <= 1008 + .01);
    assert.ok(height * scale <= 648 + .01);
  }
});
