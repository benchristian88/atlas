"use client";

import { useEffect, useRef, useState } from "react";
import { apiRequest } from "./api";
import {
  beginPendingApply, clearPendingApply, creationAllowed, readPendingApply, restrictedClassifications, selectionPayload,
  selectionState, validateCapabilities, validApplyOutcome,
} from "./onboarding-capabilities.mjs";

const request = (path, options) => apiRequest(path, { ...options, omitContext: true, cache: "no-store" });
const write = (path, method, payload, signal = AbortSignal.timeout(25_000)) =>
  request(path, { method, body: JSON.stringify(payload), signal });

const accessFailure = (error) => [401, 403, 404].includes(error.status);
const ambiguousFailure = (error) => !error.status
  || error.status === 408 || error.status === 429 || error.status >= 500 || error.kind === "response";
// A database lock timeout can return 409 before the receipt is checked.
const uncertainConflict = (error) => error.status === 409
  && error.details?.detail === "A concurrent change prevented this decision; refresh and review before retrying";

const referenceEndpoints = {
  service_type_key: ["/service-types?active_only=true", "can_view_service_types"],
  criticality_key: ["/criticality-levels?active_only=true", "can_view_criticality_levels"],
};

export function useOnboardingCapabilities({ path, profile, pendingKey, progress, visible, onProgress, onExit, onApplied, onBusy }) {
  const url = `${path}/capabilities`;
  const [data, setData] = useState(null);
  const [state, setState] = useState(null);
  const [draftRestored, setDraftRestored] = useState(false);
  const [acknowledgedStale, setAcknowledgedStale] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [preview, setPreview] = useState(null);
  const [previewAttempt, setPreviewAttempt] = useState(0);
  const [referenceAttempt, setReferenceAttempt] = useState(0);
  const [references, setReferences] = useState({});
  const [recovery, setRecovery] = useState(() => readPendingApply(pendingKey));
  const [failure, setFailure] = useState(null);
  const [busy, setBusy] = useState("");
  const operation = useRef(null);
  const mounted = useRef(false);
  const currentProgress = useRef(progress);
  const notifyProgress = useRef(onProgress);
  const previewTarget = useRef(null);
  currentProgress.current = progress;
  notifyProgress.current = onProgress;

  const selection = state && data?.catalogue ? selectionPayload(data, state) : null;
  const restricted = restrictedClassifications(data, selection);
  const original = data?.catalogue ? selectionPayload(data, selectionState(data)) : null;
  const signature = selection ? JSON.stringify(selection) : null;
  const dirty = signature !== (original && JSON.stringify(original))
    || Boolean(state && [...state.overrides.keys()].some((id) => !state.functions.has(id) && !state.services.has(id)))
    || acknowledgedStale;
  const locked = Boolean(failure?.reload || loading);
  const currentPreview = !locked && preview?.signature === signature && preview.version === data?.version
    && preview.attempt === previewAttempt ? preview : null;
  const empty = selection && !selection.functions.length && !selection.services.length;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    async function load() {
      try {
        const next = validateCapabilities(await request(url, { signal }), profile);
        if (signal.aborted) return;
        if (loadAttempt || currentProgress.current.version !== next.version) {
          const status = await request(path, { signal });
          if (signal.aborted) return;
          if (status.progress?.version !== next.version) {
            throw new Error("Shared setup progress changed while loading. Reload saved progress to try again.");
          }
          notifyProgress.current(status.progress, true, status.can_manage);
        }
        setData(next);
        setState(selectionState(next));
        setDraftRestored(Boolean(next.draft && !next.draft_stale));
        setAcknowledgedStale(false);
      } catch (error) {
        if (signal.aborted) return;
        if (accessFailure(error)) setData(null);
        setFailure({ message: accessFailure(error)
          ? "Capabilities are unavailable for this Site or your access has changed." : error.message, reload: true });
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [url, path, profile, loadAttempt]);

  const canViewTypes = data?.permissions.can_view_service_types;
  const canViewLevels = data?.permissions.can_view_criticality_levels;
  useEffect(() => {
    const controller = new AbortController();
    setReferences({});
    if (profile !== "homelab" || locked) return () => controller.abort();
    for (const [field, [endpoint, permission]] of Object.entries(referenceEndpoints)) {
      if (!(permission === "can_view_service_types" ? canViewTypes : canViewLevels)) continue;
      request(endpoint, { signal: controller.signal }).then((rows) => {
        if (!Array.isArray(rows) || rows.some((row) => typeof row?.key !== "string" || typeof row.name !== "string")) {
          throw new Error("Invalid reference data.");
        }
        if (!controller.signal.aborted) setReferences((old) => ({ ...old, [field]: { rows } }));
      }).catch((error) => {
        if (!controller.signal.aborted) setReferences((old) => ({ ...old, [field]: { error: true, access: accessFailure(error) } }));
      });
    }
    return () => controller.abort();
  }, [canViewTypes, canViewLevels, profile, locked, loadAttempt, referenceAttempt]);

  const version = data?.version;
  const canPreview = visible && data?.permissions.can_manage && signature && !empty && !restricted.size && !locked && !currentPreview
    && !busy && !recovery && (!data.draft_stale || acknowledgedStale);
  const previewKey = canPreview ? `${version}:${previewAttempt}:${signature}` : null;
  previewTarget.current = previewKey;
  useEffect(() => {
    if (!previewKey) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const result = await write(`${url}/preview`, "POST", { version, selection: JSON.parse(signature) },
          AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]));
        if (!Array.isArray(result?.warnings)
          || result.warnings.some((warning) => warning?.code !== "existing_name" || typeof warning.definition_id !== "string")) {
          throw new Error("Atlas returned an invalid preview. Try again.");
        }
        if (!controller.signal.aborted && previewTarget.current === previewKey) {
          setPreview({ signature, version, warnings: result.warnings, attempt: previewAttempt });
        }
      } catch (error) {
        if (controller.signal.aborted || previewTarget.current !== previewKey) return;
        if (error.status === 409 || accessFailure(error)) {
          setFailure({ message: error.status === 409
            ? "Shared progress or the catalogue changed. Reload saved progress and review it before continuing."
            : "Your access changed. Reload saved progress to see the operations available to you.", reload: true });
        } else {
          setPreview({ signature, version, error, attempt: previewAttempt });
        }
      }
    }, 350);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [url, version, signature, previewKey, previewAttempt]);

  function reload() {
    if (operation.current || (dirty && !window.confirm("Discard local edits and reload saved progress?"))) return false;
    setFailure(null);
    setLoading(true);
    setPreview(null);
    setLoadAttempt((value) => value + 1);
    return true;
  }

  function update(transform) {
    setState(transform);
    setPreview(null);
    setFailure(null);
  }

  function replaceStale() {
    setAcknowledgedStale(true);
    setFailure(null);
  }

  function adopt(progress) {
    setData((old) => ({ ...old, version: progress.version, draft: selection, draft_stale: false }));
    setDraftRestored(false);
    setAcknowledgedStale(false);
    onProgress(progress, true);
  }

  async function runApply(pending, retry = false) {
    let result;
    try {
      result = await write(`${url}/apply`, "POST", pending);
      if (!validApplyOutcome(result, pending)) throw new Error("Atlas returned an invalid Apply receipt.");
    } catch (error) {
      if (!mounted.current) return;
      if (ambiguousFailure(error) || uncertainConflict(error) || (retry && accessFailure(error))) {
        const access = accessFailure(error);
        setFailure({ message: access
          ? "Atlas could not confirm the Apply outcome with your current access. Reload saved progress and retry when the required permissions are available."
          : "Atlas could not confirm whether Apply finished. Retry this Apply to recover its outcome.", reload: access });
        return;
      }
      clearPendingApply(pendingKey);
      setRecovery(null);
      throw error;
    }
    if (!mounted.current) return;
    // A replayed receipt can predate another administrator's latest decision.
    try {
      const status = await request(path, { signal: AbortSignal.timeout(15_000) });
      if (!mounted.current) return;
      if (!status.progress || status.progress.version < result.version) throw new Error("Progress has not caught up.");
      clearPendingApply(pendingKey);
      setRecovery(null);
      onApplied(result, status.progress, status.can_manage);
    } catch {
      if (mounted.current) setFailure({ message: "Apply succeeded. Retry this Apply to refresh the current setup progress." });
    }
  }

  async function mutate(action) {
    if (operation.current || !data?.permissions.can_manage || locked || (recovery && action !== "retry")) return;
    if (action === "apply" && (!currentPreview || currentPreview.error || empty || !creationAllowed(data.permissions, selection))) return;
    operation.current = action;
    setBusy(action);
    onBusy(true);
    setFailure(null);
    let expected = version;
    try {
      if (action === "retry") {
        await runApply(recovery, true);
      } else if (action === "skip") {
        const next = await write(`${url}/skip`, "POST", { version });
        if (mounted.current) onProgress(next);
      } else if (profile === "blank") {
        await write(`${path}/save`, "POST", { version });
        if (mounted.current) onExit();
      } else {
        const next = await write(`${url}/draft`, "PUT", {
          version, selection, save_and_exit: action === "save", replace_stale_draft: acknowledgedStale,
        });
        if (!mounted.current) return;
        if (next?.version !== version + 1 || next.environment_profile !== profile) {
          setFailure({ message: "Atlas could not verify the saved draft. Reload saved progress before continuing.", reload: true });
          return;
        }
        expected = next.version;
        adopt(next);
        if (action === "save") onExit();
        else {
          const pending = beginPendingApply(pendingKey, next.version);
          setRecovery(pending);
          await runApply(pending);
        }
      }
    } catch (error) {
      if (!mounted.current) return;
      const detail = error.details?.detail;
      if (accessFailure(error)) {
        setPreview(null);
        setFailure({ message: "Your access changed. Reload saved progress to see the operations available to you.", reload: true });
      } else if (error.status === 409) {
        // E1-B returns plain-string conflicts. Distinguish changed workflow or
        // catalogue state from a canonical conflict without parsing messages.
        try {
          const latest = validateCapabilities(await request(url, { signal: AbortSignal.timeout(15_000) }), profile);
          if (!mounted.current) return;
          const changed = latest.version !== (action === "retry" ? recovery.version : expected)
            || latest.catalogue?.content_version !== data.catalogue?.content_version
            || latest.catalogue?.schema_version !== data.catalogue?.schema_version
            || (latest.draft_stale && !acknowledgedStale);
          setFailure(changed
            ? { message: "Shared setup progress or the catalogue changed. Reload saved progress before trying again.", reload: true }
            : { message: error.message });
        } catch {
          if (mounted.current) setFailure({ message: error.message, reload: true });
        }
      } else if (error.name === "SecurityError" || error.name === "QuotaExceededError" || error instanceof TypeError) {
        setFailure({ message: "Atlas could not store the Apply recovery ID in this browser. Allow session storage and try again." });
      } else {
        setFailure({ message: error.message, definitionId: detail?.definition_id });
      }
    } finally {
      operation.current = null;
      if (mounted.current) setBusy("");
      onBusy(false);
    }
  }

  return {
    data, state, selection, dirty, loading, locked, busy, failure, recovery, references, draftRestored, restricted,
    preview: currentPreview, acknowledgedStale, replaceStale, reload, mutate, update,
    retryPreview: () => setPreviewAttempt((value) => value + 1),
    retryReferences: () => setReferenceAttempt((value) => value + 1),
  };
}
