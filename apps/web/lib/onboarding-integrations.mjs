export function continuationCandidate(rows) {
  return rows.find(row => row.continuation_run_id) || null;
}

export function runNeedsPolling(run) {
  return ["pending", "running"].includes(run?.status)
    || Boolean(run?.dispatch_state && run.dispatch_state !== "settled");
}

export function mutationOutcomeUnknown(error) {
  const status = error?.status;
  return error?.kind === "network" || error?.kind === "response"
    || !Number.isInteger(status) || status === 408 || status >= 500;
}

export function runAppearedSinceRead(latest, previousRunId) {
  return Boolean(latest && (latest.id !== previousRunId || runNeedsPolling(latest)));
}
