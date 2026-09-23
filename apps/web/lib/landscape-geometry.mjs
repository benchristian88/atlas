const PADDING = 16;

export function fitLandscape(width, height, contentWidth, contentHeight) {
  return Math.min(1.5, Math.max(.1, Math.min(
    Math.max(1, width - PADDING * 2) / contentWidth,
    Math.max(1, height - PADDING * 2) / contentHeight,
  )));
}

// Layout is expressed in readable CSS pixels, independent of content height
// and the user's view transform. Narrow screens scroll rather than shrink text.
export function landscapeGeometry(width, expanded = false) {
  const minimumNodeWidth = expanded ? 224 : 200;
  const preferredNodeWidth = expanded ? 264 : 226;
  const inset = 24;
  const stepX = Math.max(minimumNodeWidth + inset, (width - PADDING * 2) / 3);
  return {
    stepX,
    width: stepX * 3,
    nodeWidth: Math.min(preferredNodeWidth, stepX - inset),
    nodeHeight: expanded ? 72 : 64,
  };
}
