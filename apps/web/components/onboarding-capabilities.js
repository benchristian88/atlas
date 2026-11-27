"use client";

import { useEffect, useRef, useState } from "react";
import { changeSelection, creationAllowed, editEntry, recommendedState } from "../lib/onboarding-capabilities.mjs";
import { useOnboardingCapabilities } from "../lib/use-onboarding-capabilities";
import { Button } from "./button";
import { CapabilityCatalogue, CapabilityReview, classificationProblems } from "./onboarding-capability-catalogue";
import styles from "./onboarding.module.css";

function CapabilityFeedback({ failure, preview, reload, retry, blocked, review }) {
  const feedback = useRef(null);
  useEffect(() => { if (failure || (review && preview?.error)) feedback.current?.focus(); }, [failure, review, preview?.error]);
  if (failure) return <div ref={feedback} tabIndex={-1} role="alert" className="error-banner">
    <p>{failure.message}</p>
    {failure.reload && <Button onClick={reload} disabled={blocked}>Reload saved progress</Button>}
  </div>;
  if (!preview?.error) return null;
  const invalid = [413, 422].includes(preview.error.status);
  return <div ref={feedback} tabIndex={-1} role={review ? "alert" : undefined} className="error-banner">
    <p>{preview.error.message}</p>
    {invalid ? <p>Correct or deselect the affected entries and check the selection again.</p>
      : <Button onClick={retry} disabled={blocked}>Retry preview</Button>}
  </div>;
}

function PermissionNotice({ permissions, profile }) {
  if (!permissions.can_manage) return <p>You can view {profile === "homelab" && "the catalogue and "}Site progress.
    {" "}A Site manager can save or skip this stage.</p>;
  const missing = [
    !permissions.can_create_functions && "Business Functions",
    !permissions.can_create_services && "Services",
    !permissions.can_create_associations && "Supports associations",
  ].filter(Boolean);
  if (!missing.length) return null;
  return <p className="warning-banner">Your permissions prevent creation of {missing.join(", ")}.
    {" "}Remove selections that require those permissions before applying. You can still save a valid draft
    {permissions.can_create_functions ? " or import Business Functions on their own." : "."}</p>;
}

export function OnboardingCapabilities({ path, pendingKey, progress, visible, returning,
  headingRef, home, onEnvironment, onReturn, onProgress, onExit, onApplied, onBusy }) {
  const profile = progress.environment_profile;
  const flow = useOnboardingCapabilities({ path, profile, pendingKey, progress, visible, onProgress, onExit, onApplied, onBusy });
  const [review, setReview] = useState(false);
  const [expanded, setExpanded] = useState(new Set());
  const [editing, setEditing] = useState(null);
  const reviewHeading = useRef(null);
  const { data, state, selection, dirty, preview, failure, loading, locked, busy, recovery, references, restricted } = flow;
  const additional = Boolean(progress.stage_decisions.capabilities);
  const canManage = data?.permissions.can_manage;
  const stale = data?.draft_stale && !flow.acknowledgedStale;
  const empty = selection && !selection.functions.length && !selection.services.length;
  const selected = Boolean(selection && !empty);
  const saved = progress.status === "saved";
  const editingLocked = locked || Boolean(busy || recovery || stale || saved || returning);
  const canApply = creationAllowed(data?.permissions ?? {}, selection);
  const validated = Boolean(preview && !preview.error && !restricted.size);
  const detail = failure?.definitionId ? { definition_id: failure.definitionId, message: failure.message }
    : preview?.error?.details?.detail;
  const classificationErrors = canManage && selected && !recovery
    ? classificationProblems(data, selection, references, detail) : [];
  const classificationRejection = classificationErrors.some(({ serviceId, labels }) =>
    serviceId === detail?.definition_id && labels.some((label) => detail.message?.startsWith(label)));

  useEffect(() => {
    if (visible && review) reviewHeading.current?.focus();
  }, [visible, review]);

  function selectionView() {
    setReview(false);
    requestAnimationFrame(() => headingRef.current?.focus());
  }

  function reload() {
    if (!flow.reload()) return;
    setReview(false);
    setExpanded(new Set());
    setEditing(null);
  }

  function editClassification({ groupId, serviceId, focusField }) {
    setReview(false);
    setExpanded((old) => new Set([...old, groupId]));
    setEditing({ id: serviceId, field: focusField });
  }

  function skip() {
    if ((selected || dirty || data?.draft) && !window.confirm(
      "Skip Capabilities and discard this selection? This creates no Business Functions or Services.",
    )) return;
    flow.mutate("skip");
  }

  function restore() {
    if (state.overrides.size && !window.confirm("Restore catalogue recommendations and discard all customised values?")) return;
    flow.update(() => recommendedState(data));
  }

  return <>
    {profile === "homelab" && <div className={styles.capabilityIntro}>
      {data?.catalogue && <p className={styles.catalogueVersion}>Catalogue version {data.catalogue.content_version}</p>}
      <p>Capabilities are created for this Customer and can be available to other authorized Sites.
        {" "}Setup progress belongs to this Site.</p>
    </div>}
    <CapabilityFeedback failure={classificationRejection ? null : failure}
      preview={classificationRejection ? null : preview} review={review}
      reload={reload} retry={flow.retryPreview} blocked={Boolean(busy || editing || loading)} />
    {classificationErrors.length > 0 && <div className={classificationRejection ? "error-banner" : "warning-banner"}
      role="region" aria-label="Unavailable classifications">
      <p role={classificationRejection ? "alert" : "status"}>Choose an active classification or deselect each affected Service.</p>
      <ul className={styles.classificationErrors}>
        {classificationErrors.map((issue) => <li key={issue.serviceId}>
          <p><strong>{issue.name}</strong> · {issue.labels.join(" and ")} unavailable</p>
          <Button onClick={() => editClassification(issue)} disabled={editingLocked || Boolean(editing)}
            aria-label={`Edit classifications for ${issue.name}`}>Edit classifications</Button>
        </li>)}
      </ul>
    </div>}
    {loading && <p role="status">Loading Capabilities…</p>}
    {recovery && <>
      <p className={busy === "apply" ? undefined : "warning-banner"} role="status">
        {busy === "apply" ? "Applying capabilities…"
          : "An Apply is awaiting confirmation. Retry the original request to retrieve its outcome safely."}
      </p>
      <div className={styles.actions}>
        {canManage && <Button variant="primary" loading={busy === "retry"} disabled={locked}
          onClick={() => flow.mutate("retry")}>{busy === "retry" ? "Checking Apply…" : "Retry this Apply"}</Button>}
        {!canManage && data && <p>A Site manager with the required creation permissions can confirm the outcome using the original session.</p>}
        <Button href={home} disabled={Boolean(busy)}>Return to Atlas</Button>
      </div>
    </>}
    {!recovery && data && <>
      {(profile === "homelab" || !canManage) && <PermissionNotice permissions={data.permissions} profile={profile} />}
      {additional && <p>Additional import. Apply creates new records and preserves the current setup stage.</p>}
      {flow.draftRestored && !review && <p className={styles.capabilityStatus} role="status">Saved selection restored.</p>}
      {data.draft_stale && <div className="warning-banner">
        <p>The saved draft uses an earlier catalogue version. Review the installed catalogue before replacing the draft.</p>
        {canManage && !flow.acknowledgedStale && <Button disabled={locked || Boolean(busy) || saved}
          onClick={flow.replaceStale}>Review current catalogue</Button>}
        {flow.acknowledgedStale && <p>Saving or applying the reviewed selection will replace the earlier draft.</p>}
      </div>}
      {Object.values(references).some((reference) => reference.error) && <div className="warning-banner">
        <p>Some managed classifications could not be loaded. Atlas checks selected classifications when validating the draft.</p>
        <Button onClick={flow.retryReferences} disabled={Boolean(busy || locked)}>Retry classification data</Button>
      </div>}
      {canManage && restricted.size > 0 && <p className="warning-banner">
        Some selected Services use customised classifications that your permissions do not cover.
        {" "}Restore their catalogue defaults or deselect those Services.
      </p>}
      {profile === "blank" ? <p>Blank is a manual setup. You can add Business Functions and Services in Atlas whenever you need them.</p>
        : review ? <>
          <h3 tabIndex={-1} ref={reviewHeading}>Review capabilities</h3>
          <p>Apply creates the following Customer-wide records. Existing records will stay as they are.</p>
          <CapabilityReview data={data} state={state} selection={selection} preview={preview} references={references} restricted={restricted} />
          {!canApply && <p className="warning-banner">Your current permissions do not allow this selection to be applied.</p>}
        </> : <>
          <h3>What does your Homelab support?</h3>
          <p>Choose from the bundled starter catalogue and add more capabilities later.</p>
          {canManage && <div className={styles.actions}>
            <Button disabled={editingLocked || Boolean(editing) || !creationAllowed(data.permissions,
              { functions: [true], services: [true], associations: [true] })}
              onClick={restore}>Restore recommended selection</Button>
          </div>}
          <CapabilityCatalogue data={data} state={state} disabled={editingLocked} selection={selection}
            references={references} preview={preview} restricted={restricted} failure={failure} expanded={expanded} setExpanded={setExpanded}
            editing={editing} setEditing={setEditing}
            reviewAction={canManage && <Button className={styles.desktopReview} variant="primary"
              disabled={editingLocked || Boolean(editing) || !selected} onClick={() => setReview(true)}>Review selection</Button>}
            onSelection={(group, change) => flow.update((old) => changeSelection(old, data.catalogue, group, change))}
            onEdit={(definition, values) => flow.update((old) => editEntry(old, data, definition, values))} />
          {empty && <p>No capabilities selected. Choose a Business Function to start.</p>}
        </>}
      {selected && canManage && !preview && !failure && !editingLocked && !restricted.size && <p role="status">Checking selection…</p>}
      {review && validated && <p role="status">Atlas validated this selection.</p>}
      {busy && busy !== "retry" && <p role="status">
        {busy === "apply" ? "Applying capabilities…" : busy === "skip" ? "Skipping Capabilities…" : "Saving selection…"}
      </p>}
      {!additional && canManage && profile === "homelab" && <p>Skipping creates no Business Functions or Services.</p>}
      <div className={styles.footer}>
        {review ? <Button disabled={Boolean(busy)} onClick={selectionView}>Back to selection</Button>
          : <Button onClick={onEnvironment} disabled={Boolean(busy || editing)}>Back to Environment</Button>}
        {additional && <Button disabled={Boolean(busy || editing)} loading={returning} onClick={() => {
          if (!dirty || window.confirm("Discard local edits and return to the current stage?")) onReturn();
        }}>Return to current stage</Button>}
        {!canManage || saved ? <Button href={home}>Return to Atlas</Button>
          : <>
            {!additional && !review && <Button disabled={locked || Boolean(busy || editing || returning)} onClick={skip}>
              Skip capabilities
            </Button>}
            {!review && <Button loading={busy === "save"} disabled={editingLocked || Boolean(editing) || restricted.size > 0
                || Boolean(preview?.error && [413, 422].includes(preview.error.status))}
              onClick={() => flow.mutate("save")}>Save &amp; exit</Button>}
            {profile === "homelab" && (review
              ? <Button variant="primary" loading={busy === "apply"}
                  disabled={editingLocked || !selected || !canApply || !validated}
                  onClick={() => flow.mutate("apply")}>Apply capabilities</Button>
              : <Button className={styles.mobileReview} variant="primary" disabled={editingLocked || Boolean(editing) || !selected}
                  onClick={() => setReview(true)}>Review selection</Button>)}
          </>}
      </div>
    </>}
    {!data && !loading && !recovery && <Button href={home}>Return to Atlas</Button>}
  </>;
}
