"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../lib/api";
import { officialCatalogueBlocked, officialCatalogueDiagnostic, officialCatalogueRequestError, readOfficialCatalogueStatus } from "../lib/integrations.mjs";
import { OfficialCataloguePanel } from "./integration-panels";

export function OfficialCatalogue({ canManage, styles }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState(null);
  const operation = useRef(null);
  const generation = useRef(0);

  const reload = useCallback(async () => {
    if (operation.current) return;
    const controller = new AbortController();
    operation.current = controller;
    const current = ++generation.current;
    setLoading(true); setError("");
    try {
      const next = readOfficialCatalogueStatus(await apiRequest("/integration-catalogue/status", { omitContext: true, signal: controller.signal }));
      if (current === generation.current) { setStatus(next); setFeedback(null); }
    } catch (failure) {
      if (current === generation.current) {
        if ([401, 403].includes(failure.status)) { setStatus(null); setFeedback(null); }
        setError(officialCatalogueRequestError(failure));
      }
    } finally {
      if (current === generation.current) { operation.current = null; setLoading(false); }
    }
  }, []);

  useEffect(() => {
    reload();
    return () => { generation.current += 1; operation.current?.abort(); operation.current = null; };
  }, [reload]);

  async function refresh() {
    if (!canManage || !status || error || operation.current || officialCatalogueBlocked(status) || ["cooldown", "in_progress"].includes(feedback?.result)) return;
    const controller = new AbortController();
    operation.current = controller;
    const current = ++generation.current;
    setRefreshing(true); setFeedback(null); setError("");
    try {
      const response = await apiRequest("/integration-catalogue/refresh", { method: "POST", omitContext: true, signal: controller.signal });
      if (current !== generation.current) return;
      if (!["accepted", "unchanged", "in_progress", "cooldown", "failed"].includes(response?.result)) throw new Error("Unexpected refresh result");
      const next = response.status ? readOfficialCatalogueStatus(response.status, { requireEntries: false }) : null;
      if (response.result !== "failed" && !next) throw new Error("Missing refresh status");
      if (["accepted", "unchanged"].includes(response.result) && (!next.trusted_remote_available || next.refresh_state === "failed" || next.last_error_code || next.source_conflict)) throw new Error("Inconsistent refresh status");
      // Refresh returns checkpoint status only, never entries. Preserve existing
      // metadata until the independent GET supplies the complete projection.
      if (next) setStatus(previous => previous?.trusted_remote_available
        && (previous.sequence !== next.sequence || previous.content_digest !== next.content_digest)
        ? previous : { ...next, entries: previous?.entries || [] });
      const result = response.result;
      setFeedback({ result, message: {
        accepted: "Official catalogue verified and accepted.",
        unchanged: "Official catalogue verified; the accepted catalogue is unchanged.",
        in_progress: "An official catalogue check is already in progress. Reload status to see its result.",
        cooldown: "Official catalogue checks are temporarily unavailable. Reload status after the next permitted check time.",
        failed: officialCatalogueDiagnostic(next || { ...status, last_error_code: response.code }),
      }[result] });
      const complete = readOfficialCatalogueStatus(await apiRequest("/integration-catalogue/status", { omitContext: true, signal: controller.signal }));
      if (current === generation.current) setStatus(complete);
    } catch (failure) {
      if (current === generation.current) {
        if ([401, 403].includes(failure.status)) { setStatus(null); setFeedback(null); }
        setError(officialCatalogueRequestError(failure));
      }
    } finally {
      if (current === generation.current) { operation.current = null; setRefreshing(false); }
    }
  }

  return <OfficialCataloguePanel status={status} loading={loading} refreshing={refreshing} error={error} feedback={feedback} canManage={canManage} onRefresh={refresh} onReload={reload} styles={styles} />;
}
