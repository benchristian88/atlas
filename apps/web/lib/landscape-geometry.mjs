const PADDING = 16;

export function fitLandscape(width, height, contentWidth, contentHeight) {
  return Math.min(1.5, Math.max(.1, Math.min(
    Math.max(1, width - PADDING * 2) / contentWidth,
    Math.max(1, height - PADDING * 2) / contentHeight,
  )));
}

// Widen the lanes in world coordinates when height limits uniform card scale.
// Cards and vertical geometry stay unchanged; connectors follow the new positions.
export function landscapeGeometry(width, height, contentHeight) {
  const scale = fitLandscape(width, height, 990, contentHeight);
  const stepX = Math.max(330, (width - PADDING * 2) / scale / 3);
  return { stepX, width: stepX * 3 };
}
