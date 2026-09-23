import test from "node:test";
import assert from "node:assert/strict";
import { landscapeGeometry, fitLandscape } from "../lib/landscape-geometry.mjs";

test("expanded lanes use available width even when height limits fit", () => {
  for (const [width, height, contentHeight] of [[1040, 680, 1240], [1400, 680, 1240], [1040, 680, 300], [700, 480, 1240]]) {
    const layout = landscapeGeometry(width, height, contentHeight);
    const zoom = fitLandscape(width, height, layout.width, contentHeight);
    assert.ok(Math.abs(layout.width * zoom - (width - 32)) < .01);
    assert.ok(contentHeight * zoom <= height - 32 + .01);
    assert.ok(layout.stepX >= 330);
  }
});
test("inspector and resize geometry is reversible and embedded fit is independent", () => {
  const visible = landscapeGeometry(1040, 680, 1240);
  const hidden = landscapeGeometry(1400, 680, 1240);
  assert.ok(hidden.stepX > visible.stepX);
  assert.deepEqual(landscapeGeometry(1040, 680, 1240), visible);
  assert.notEqual(fitLandscape(700, 660, 990, 1240), fitLandscape(1400, 800, hidden.width, 1240));
});
