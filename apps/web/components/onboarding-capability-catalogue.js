"use client";

import { useEffect, useId, useRef, useState } from "react";
import { entryDefaults, hasCustomisations, orderedDefinitions } from "../lib/onboarding-capabilities.mjs";
import { Button } from "./button";
import { Surface } from "./section";
import styles from "./onboarding.module.css";

const classifications = [
  ["service_type_key", "Service Type", "can_view_service_types", "service_type_name"],
  ["criticality_key", "Criticality", "can_view_criticality_levels", "criticality_name"],
];
const restrictedMessage = "Restore catalogue defaults or deselect this Service to continue with your current permissions.";

function ExistingName({ entry, service }) {
  return <p className={styles.nameWarning}>A {service ? "Service" : "Business Function"} named “{entry.name.trim()}” already exists.
    {" "}Rename or deselect this entry if needed.</p>;
}

export function classificationProblems(data, selection, references, detail) {
  const selected = new Map(selection.services.map((item) => [item.id, item]));
  // Preview identifies the first invalid definition. The active reference lists
  // can identify other affected Services in the same selection.
  const invalidField = classifications.find(([, label]) => detail?.message?.startsWith(label))?.[0];
  return data.catalogue.functions.flatMap((group) => group.services.flatMap((service) => {
    const item = selected.get(service.id);
    if (!item) return [];
    const values = { ...entryDefaults(data, service), ...item };
    const fields = classifications.filter(([field]) =>
      (detail?.definition_id === service.id && field === invalidField)
      || (references[field]?.rows && !references[field].rows.some(({ key }) => key === values[field])));
    return fields.length ? [{
      groupId: group.id, serviceId: service.id, name: values.name,
      labels: fields.map(([, label]) => label),
      focusField: fields.find(([, , permission]) => data.permissions[permission])?.[0],
    }] : [];
  }));
}

function ReferenceSelect({ field, label, value, reference, permitted, onChange, inputRef }) {
  const id = useId();
  const rows = reference?.rows ?? [];
  const listed = rows.some(({ key }) => key === value);
  const unavailable = !permitted || reference?.error || !reference;
  const help = !permitted || reference?.access ? "Your permissions limit access to these values."
    : reference?.error ? "Use Retry classification data to load these values again."
      : !reference ? "Loading active values…"
        : !listed ? "Choose an active value or deselect this Service." : null;
  return <div className="field">
    <label htmlFor={id}>{label}</label>
    <select id={id} ref={inputRef} aria-invalid={Boolean(reference?.rows && !listed) || undefined}
      aria-describedby={help ? `${id}-help` : undefined}
      value={value ?? ""} disabled={unavailable} onChange={(event) => onChange(field, event.target.value)}>
      {!listed && <option value={value ?? ""} disabled>{unavailable ? "Current selection" : "Choose an active value"}</option>}
      {rows.map(({ key, name }) => <option key={key} value={key}>{name}</option>)}
    </select>
    {help && <small id={`${id}-help`}>{help}</small>}
  </div>;
}

function EntryEditor({ entry, definition, data, references, onSave, onRestore, onClose, customised, focusField }) {
  const [fields, setFields] = useState(entry);
  const name = useRef(null);
  const classification = useRef(null);
  const id = useId();
  const nameTooLong = Array.from(fields.name ?? "").length > 255;
  const descriptionTooLong = Array.from(fields.description ?? "").length > 20_000;
  const valid = Boolean(fields.name?.trim()) && !nameTooLong && !descriptionTooLong;
  useEffect(() => {
    const target = classification.current;
    (target && !target.disabled ? target : name.current)?.focus();
  }, []);
  function change(field, value) {
    setFields((old) => ({ ...old, [field]: value }));
  }

  return <form aria-labelledby={`${id}-title`} className={styles.editor} onSubmit={(event) => {
    event.preventDefault();
    if (valid) onSave(fields);
  }}>
    <h4 id={`${id}-title`}>Edit {definition.name}</h4>
    <div className="field">
      <label htmlFor={`${id}-name`}>Name</label>
      <input id={`${id}-name`} ref={name} required value={fields.name ?? ""} maxLength={510}
        aria-invalid={nameTooLong || undefined} aria-describedby={nameTooLong ? `${id}-name-error` : undefined}
        onChange={(event) => change("name", event.target.value)} />
      {nameTooLong && <small id={`${id}-name-error`}>Use 255 characters or fewer.</small>}
    </div>
    <div className="field">
      <label htmlFor={`${id}-description`}>Description</label>
      <textarea id={`${id}-description`} rows={3} maxLength={40_000} value={fields.description ?? ""}
        aria-invalid={descriptionTooLong || undefined} aria-describedby={descriptionTooLong ? `${id}-description-error` : undefined}
        onChange={(event) => change("description", event.target.value || null)} />
      {descriptionTooLong && <small id={`${id}-description-error`}>Use 20,000 characters or fewer.</small>}
    </div>
    {definition.business_function_id && <div className={styles.fields}>
      {classifications.map(([field, label, permission]) =>
        <ReferenceSelect key={field} field={field} label={label} value={fields[field]} reference={references[field]}
          permitted={data.permissions[permission]} onChange={change} inputRef={field === focusField ? classification : undefined} />)}
    </div>}
    <div className={styles.actions}>
      <Button type="submit" variant="primary" disabled={!valid}>Save edit</Button>
      <Button onClick={onClose}>Cancel edit</Button>
      {customised && <Button onClick={onRestore}>Restore catalogue defaults</Button>}
    </div>
  </form>;
}

function Entry({ definition, entry, customised, selected, warning, validation, data, references,
  editable, toggleDisabled, onToggle, editing, onEdit, onClose, onSave, onRestore, children, count }) {
  const editButton = useRef(null);
  const checkId = useId();
  const isEditing = editing?.id === definition.id;
  const service = Boolean(definition.business_function_id);
  const Title = service ? "h6" : "h4";
  const name = entry.name ?? definition.name;
  function close() {
    onClose();
    requestAnimationFrame(() => editButton.current?.focus());
  }
  return <>
    <div className={styles.entryHeader}>
      <div className={styles.entryIdentity}>
        <div className={styles.entryCheck}>
          <input id={checkId} type="checkbox" checked={selected} disabled={toggleDisabled}
            aria-label={`Select ${name}`} aria-describedby={count ? `${checkId}-count` : undefined}
            onChange={(event) => onToggle(event.target.checked)} />
          <Title><label htmlFor={checkId}>{name}</label></Title>
        </div>
        {count && <small id={`${checkId}-count`}>{count}</small>}
      </div>
      <div className={styles.entryActions}>
        {children}
        <Button variant="quiet" ref={editButton} aria-label={`Edit ${name}`}
          disabled={!editable || Boolean(editing)} onClick={onEdit}>Edit</Button>
      </div>
    </div>
    {!isEditing && entry.description && <p className={styles.entryDescription}>{entry.description}</p>}
    {!isEditing && service && <Classification entry={entry} definition={definition} data={data} references={references} />}
    {customised && <p className={styles.customised}>Customised</p>}
    {warning && <ExistingName entry={{ ...entry, name }} service={service} />}
    {validation && <p className={styles.entryError}>{validation}</p>}
    {isEditing && <EntryEditor entry={entry} definition={definition} data={data} references={references}
      customised={customised} focusField={editing.field} onClose={close} onSave={(fields) => {
        onSave(definition, fields);
        close();
      }} onRestore={() => {
        onRestore(definition);
        close();
      }} />}
  </>;
}

function Classification({ entry, definition, data, references }) {
  const defaults = entryDefaults(data, definition);
  return <dl className={styles.classifications}>
    {classifications.map(([field, label, permission, labelKey]) => {
      const value = entry[field];
      const reference = references[field];
      const name = reference?.rows?.find(({ key }) => key === value)?.name;
      const fallback = value === defaults[field] ? definition[labelKey] : "Custom value";
      let status = "";
      if (!data.permissions[permission] || reference?.access) status = " · restricted";
      else if (reference?.rows && !name) status = " · unavailable";
      else if (reference?.error) status = " · could not verify";
      return <div key={field}><dt>{label}</dt><dd>{name ?? fallback}{status}</dd></div>;
    })}
  </dl>;
}

export function SelectionCounts({ selection }) {
  return <dl className={styles.counts}>
    {[
      ["functions", "Business Functions"], ["services", "Services"], ["associations", "Supports associations"],
    ].map(([field, label]) => <div key={field}><dt>{label}</dt><dd>{selection[field].length}</dd></div>)}
  </dl>;
}

export function CapabilityCatalogue({ data, state, disabled, selection, preview, references, editing,
  setEditing, expanded, setExpanded, onSelection, onEdit, reviewAction, restricted, failure }) {
  const { catalogue, permissions } = data;
  const warningIDs = new Set(preview?.warnings?.map(({ definition_id }) => definition_id));
  const detail = failure?.definitionId ? { definition_id: failure.definitionId, message: failure.message }
    : preview?.error?.details?.detail;
  const canSelectService = permissions.can_create_functions && permissions.can_create_services && permissions.can_create_associations;
  function values(definition) {
    return { ...entryDefaults(data, definition), ...state.overrides.get(definition.id) };
  }
  function entryProps(definition, selected, canSelect) {
    return {
      definition, data, references, editing, selected, entry: values(definition),
      customised: hasCustomisations(data, definition, state.overrides.get(definition.id)),
      warning: warningIDs.has(definition.id),
      validation: restricted.has(definition.id) ? restrictedMessage
        : detail?.definition_id === definition.id ? detail.message : null,
      editable: permissions.can_manage && !disabled && selected,
      toggleDisabled: !permissions.can_manage || disabled || Boolean(editing) || (!selected && !canSelect),
      onEdit: () => setEditing({ id: definition.id }),
      onClose: () => setEditing(null),
      onSave: onEdit,
      onRestore: (definition) => onEdit(definition, {}),
    };
  }

  return <div className={styles.catalogueGrid}>
    <div className={styles.cards} aria-label="Business Function cards">
      {orderedDefinitions(catalogue.functions).map((group) => {
        const groupSelected = state.functions.has(group.id);
        const isExpanded = expanded.has(group.id);
        const id = `catalogue-${group.id}`;
        const selectedCount = group.services.filter(({ id }) => state.services.has(id)).length;
        const services = orderedDefinitions(group.services);
        return <Surface key={group.id} className={styles.functionCard} data-definition-id={group.id}>
          <Entry {...entryProps(group, groupSelected, permissions.can_create_functions)}
            count={`${selectedCount} of ${services.length} Services selected`}
            onToggle={(selected) => onSelection(group, { selected, canSelectService })}>
            <Button aria-expanded={isExpanded} aria-controls={id}
              disabled={group.id === editing?.id || group.services.some(({ id }) => id === editing?.id)}
              aria-label={`${isExpanded ? "Hide" : "Show"} Services for ${values(group).name}`}
              onClick={() => setExpanded((old) => {
                const next = new Set(old);
                if (next.has(group.id)) next.delete(group.id);
                else next.add(group.id);
                return next;
              })}>{isExpanded ? "Hide Services" : "Show Services"}</Button>
          </Entry>
          {!groupSelected && selectedCount > 0 &&
            <p className={styles.capabilityStatus}>Selected Services will be imported without this Business Function.</p>}
          {!isExpanded && group.services.some(({ id }) => warningIDs.has(id)) &&
            <p className={styles.nameWarning}>A selected Service has an existing-name warning.</p>}
          {!isExpanded && group.services.some((service) => hasCustomisations(data, service, state.overrides.get(service.id))) &&
            <p className={styles.customised}>Includes customised Services</p>}
          <div id={id} hidden={!isExpanded}>
            {isExpanded && <div className={styles.serviceGroups}>
              <div className={styles.actions}>
                <Button variant="quiet" disabled={!canSelectService || disabled || Boolean(editing) || selectedCount === services.length}
                  onClick={() => onSelection(group, { selected: true, all: true })}>Select all Services</Button>
              </div>
              {[["standard", "Standard capabilities", "Recommended"], ["extended", "Extended capabilities", "Optional"]]
                .map(([tier, title, label]) => <section className={styles.serviceGroup} key={tier}>
                  <h5>{title} <small>{label}</small></h5>
                  <ul>{services.filter((service) => service.selection_tier === tier).map((service) =>
                    <li key={service.id} data-definition-id={service.id}>
                      <Entry {...entryProps(service, state.services.has(service.id), canSelectService)}
                        onToggle={(selected) => onSelection(group, { service, selected })} />
                    </li>)}</ul>
                </section>)}
            </div>}
          </div>
        </Surface>;
      })}
    </div>
    <Surface className={styles.selectionSummary} role="region" aria-label="Selection summary">
      <h4>Selection summary</h4>
      <div role="status" aria-atomic="true"><SelectionCounts selection={selection} /></div>
      {reviewAction}
    </Surface>
  </div>;
}

export function CapabilityReview({ data, state, selection, preview, references, restricted }) {
  const groups = orderedDefinitions(data.catalogue.functions);
  const services = groups.flatMap((group) => orderedDefinitions(group.services)).filter(({ id }) => state.services.has(id));
  const links = data.catalogue.associations.filter(({ id }) => state.associations.has(id));
  const linkedIds = new Set(links.map(({ service_id }) => service_id));
  const unlinked = services.filter(({ id }) => !linkedIds.has(id));
  const warningIDs = new Set(preview?.warnings?.map(({ definition_id }) => definition_id));
  const definitionError = preview?.error?.details?.detail?.definition_id;
  function item(definition) {
    const overrides = state.overrides.get(definition.id) ?? {};
    const entry = { ...entryDefaults(data, definition), ...overrides };
    return <>
      <strong>{entry.name}</strong>
      {hasCustomisations(data, definition, overrides) && <span className={styles.customised}> · Customised</span>}
      {entry.description !== definition.description && <details className={styles.reviewDescription}>
        <summary>Customised description for {entry.name}</summary>
        <p>{entry.description || "Description cleared."}</p>
      </details>}
      {definition.business_function_id && <Classification entry={entry} definition={definition} data={data} references={references} />}
      {warningIDs.has(definition.id) && <ExistingName entry={entry} service={Boolean(definition.business_function_id)} />}
      {definitionError === definition.id && <p className={styles.entryError}>{preview.error.message}</p>}
      {restricted.has(definition.id) && <p className={styles.entryError}>{restrictedMessage}</p>}
    </>;
  }

  return <>
    <SelectionCounts selection={selection} />
    {selection.functions.length > 0 && <ul className={styles.reviewList}>
      {groups.filter(({ id }) => state.functions.has(id)).map((group) => {
        const linked = orderedDefinitions(group.services).filter(({ id }) => linkedIds.has(id));
        return <li key={group.id}>{item(group)}
          {linked.length ? <ul aria-label="Services that support this Business Function">
            {linked.map((service) => <li key={service.id}>{item(service)}</li>)}
          </ul> : <p>No Supports associations selected for this Business Function.</p>}
        </li>;
      })}
    </ul>}
    {unlinked.length > 0 && <>
      <h4>Services without a Supports association</h4>
      <ul className={styles.reviewList}>{unlinked.map((service) => <li key={service.id}>{item(service)}</li>)}</ul>
    </>}
  </>;
}
