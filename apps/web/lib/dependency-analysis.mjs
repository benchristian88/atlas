export const ANALYSIS_STATE_LABELS = {
  unavailable: "Unavailable",
  degraded: "Degraded",
  unknown: "Unknown",
  unaffected: "Unaffected by this scenario",
};

export const ANALYSIS_CLASSIFICATION_LABELS = {
  direct: "Direct consequence",
  downstream: "Downstream consequence",
};

export function previewUnavailable(apiRequest, focusType, focusId) {
  return apiRequest("/dependency-analysis", {
    method: "POST",
    body: JSON.stringify({ focus_type: focusType, focus_id: focusId, state: "unavailable" }),
  });
}
