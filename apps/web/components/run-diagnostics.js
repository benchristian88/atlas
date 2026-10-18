"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { DiagnosticsView } from "./discovery-diagnostics";

export function RunDiagnostics({ run, canDebug }) {
  const [expanded, setExpanded] = useState(false), [trace, setTrace] = useState(null);
  const [error, setError] = useState(""), [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!canDebug || !run.debug_enabled || !expanded) return;
    let active = true;
    const load = () => apiRequest(`/discovery-runs/${run.id}/debug-trace`).then(value => { if (active) { setTrace(value); setError(""); } }).catch(reason => { if (active) setError(reason.message); });
    load();
    const timer = setInterval(load, 3000);
    return () => { active = false; clearInterval(timer); };
  }, [canDebug, run.id, run.debug_enabled, expanded]);
  async function remove() {
    setBusy(true); setError("");
    try { await apiRequest(`/discovery-runs/${run.id}/debug-trace`, { method: "DELETE" }); setTrace(await apiRequest(`/discovery-runs/${run.id}/debug-trace`)); }
    catch (reason) { setError(reason.message); } finally { setBusy(false); }
  }
  return <DiagnosticsView run={run} canDebug={canDebug} trace={trace} expanded={expanded} onExpand={setExpanded} onDelete={remove} busy={busy} error={error} />;
}
