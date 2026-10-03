"use client";

import { IconButton, Button } from "./button";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest } from "../lib/api";
import { DataTable } from "./data-table";
import { NavigationIcon } from "./navigation-icon.mjs";
import { PageHeader } from "./page-header";

const EMPTY_DEPENDENCIES = [];

function valueForInput(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function capabilityAllows(capability, record) {
  return typeof capability === "function" ? Boolean(capability(record)) : Boolean(capability);
}

function hookValue(hook, record, fallback) {
  if (typeof hook === "function") return hook(record);
  return hook ?? fallback;
}

export function CrudScreen({
  eyebrow,
  title,
  singularTitle = title.replace(/s$/, ""),
  description,
  endpoint,
  listEndpoint = endpoint,
  fields,
  columns,
  emptyValues,
  dependencies = EMPTY_DEPENDENCIES,
  preparePayload = (form) => form,
  canCreate = true,
  canEdit = true,
  canDelete = true,
  deleteLabel,
  deleteReason,
  contextReloadKey,
  onMutation,
  headingActions,
  reorderable = false,
}) {
  const dependencySignature = JSON.stringify(
    dependencies.map((dependency) => [dependency.key, dependency.endpoint]),
  );
  // Some callers build dependency arrays inline. Keep the loader stable until
  // the actual dependency endpoints change so a state update cannot cause a loop.
  const stableDependencies = useMemo(() => dependencies, [dependencySignature]);
  const [records, setRecords] = useState([]);
  const [related, setRelated] = useState({});
  const [form, setForm] = useState(emptyValues);
  const [editingId, setEditingId] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [items, ...relatedResults] = await Promise.all([
        apiRequest(listEndpoint),
        ...stableDependencies.map((dependency) => apiRequest(dependency.endpoint)),
      ]);
      setRecords(items);
      setRelated(
        Object.fromEntries(stableDependencies.map(
          (dependency, index) => [dependency.key, relatedResults[index]],
        )),
      );
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [listEndpoint, stableDependencies]);

  useEffect(() => {
    load();
  }, [contextReloadKey, load]);

  const relatedById = useMemo(() => Object.fromEntries(
    Object.entries(related).map(([key, values]) => [
      key,
      Object.fromEntries(values.map((value) => [value.id, value])),
    ]),
  ), [related]);

  function openCreate() {
    setEditingId(null);
    setForm(emptyValues);
    setFormOpen(true);
    setError("");
  }

  function openEdit(record) {
    setEditingId(record.id);
    setForm(Object.fromEntries(Object.keys(emptyValues).map((key) => {
      const field = fields.find((item) => item.name === key);
      const value = field?.valueFromRecord ? field.valueFromRecord(record) : record[key];
      if (field?.type === "checkbox") return [key, Boolean(value)];
      if (field?.type === "multiselect") return [key, Array.isArray(value) ? value : []];
      return [key, valueForInput(value)];
    })));
    setFormOpen(true);
    setError("");
  }

  function closeForm() {
    setFormOpen(false);
    setEditingId(null);
    setForm(emptyValues);
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = preparePayload(form, editingId);
      await apiRequest(editingId ? `${endpoint}/${editingId}` : endpoint, {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      closeForm();
      await load();
      if (onMutation) await onMutation();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(record) {
    const label = hookValue(
      deleteLabel,
      record,
      record.name || record.display_name || record.label || "this record",
    );
    const reason = hookValue(deleteReason, record, "This cannot be undone.");
    const reasonText = reason ? ` ${reason}` : "";
    if (!window.confirm(`Delete “${label}”?${reasonText}`)) return;
    setError("");
    try {
      await apiRequest(`${endpoint}/${record.id}`, { method: "DELETE" });
      await load();
      if (onMutation) await onMutation();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function move(record, direction) {
    setSaving(true);
    setError("");
    try {
      const items = await apiRequest(`${endpoint}/${record.id}/move`, {
        method: "POST", body: JSON.stringify({ direction }),
      });
      setRecords(items);
      if (onMutation) await onMutation();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  const showCreate = capabilityAllows(canCreate);
  const showActions = canEdit !== false || canDelete !== false;

  return (
    <>
      <PageHeader eyebrow={eyebrow} title={title} description={description} actions={<>{(headingActions || showCreate) && <div className="row-actions crud-heading-actions">
          {headingActions}
          {showCreate && (
            <Button variant="primary" onClick={openCreate} type="button">
              Add {singularTitle}
            </Button>
          )}
        </div>}</>} />

      {error && <div className="error-banner" role="alert">{error}</div>}

      {formOpen && (
        <section className="form-card">
          <div className="form-card-header">
            <h2>{editingId ? `Edit ${singularTitle}` : `Add ${singularTitle}`}</h2>
            <IconButton onClick={closeForm} type="button" label="Close form" icon="close" />
          </div>
          <form className="resource-form" onSubmit={submit}>
            <div className="form-grid">
              {fields.map((field) => {
                const unfilteredOptions = field.optionsKey ? related[field.optionsKey] || [] : field.options || [];
                const options = field.optionsFilter
                  ? unfilteredOptions.filter((option) => field.optionsFilter(option, form))
                  : unfilteredOptions;
                const optionValue = (option) => field.optionValue
                  ? field.optionValue(option)
                  : option.id ?? option.value;
                const fieldDisabled = Boolean(
                  (field.createOnly && editingId)
                  || (typeof field.disabled === "function"
                    ? field.disabled(form, editingId)
                    : field.disabled),
                );
                if (field.render) return <div className="field-wide" key={field.name}>{field.render({ form, setForm, disabled: fieldDisabled })}</div>;
                return (
                  <label
                    className={`${field.wide ? "field field-wide" : "field"}${field.type === "checkbox" ? " checkbox-field" : ""}`}
                    key={field.name}
                  >
                    <span>{field.label}{field.required ? " *" : ""}</span>
                    {field.type === "checkbox" ? (
                      <input
                        checked={Boolean(form[field.name])}
                        disabled={fieldDisabled}
                        name={field.name}
                        onChange={(event) => setForm({ ...form, [field.name]: event.target.checked })}
                        type="checkbox"
                      />
                    ) : field.type === "textarea" ? (
                      <textarea
                        name={field.name}
                        disabled={fieldDisabled}
                        onChange={(event) => setForm({ ...form, [field.name]: event.target.value })}
                        required={field.required}
                        rows={field.rows || 3}
                        value={form[field.name]}
                      />
                    ) : field.type === "select" || field.type === "multiselect" ? (
                      <select
                        name={field.name}
                        disabled={fieldDisabled}
                        multiple={field.type === "multiselect"}
                        onChange={(event) => {
                          const value = field.type === "multiselect"
                            ? [...event.target.selectedOptions].map((option) => option.value)
                            : event.target.value;
                          setForm({
                            ...form,
                            [field.name]: value,
                            ...Object.fromEntries((field.clearFields || []).map((name) => [name, ""])),
                          });
                        }}
                        required={field.required}
                        size={field.type === "multiselect" ? field.size || 6 : undefined}
                        value={form[field.name] ?? (field.type === "multiselect" ? [] : "")}
                      >
                        {field.type !== "multiselect" && !field.required && <option value="">{field.emptyLabel || "None"}</option>}
                        {field.type !== "multiselect" && field.placeholder && <option value="">{field.placeholder}</option>}
                        {field.type !== "multiselect" && form[field.name] && !options.some((option) => optionValue(option) === form[field.name]) && (
                          <option value={form[field.name]}>{form[field.name]} (existing custom value)</option>
                        )}
                        {options.map((option) => (
                          <option key={optionValue(option)} value={optionValue(option)}>
                            {field.optionLabel ? field.optionLabel(option, relatedById) : option.name ?? option.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        name={field.name}
                        disabled={fieldDisabled}
                        onChange={(event) => setForm({ ...form, [field.name]: event.target.value })}
                        placeholder={field.placeholder}
                        required={field.required}
                        type={field.type || "text"}
                        value={form[field.name]}
                      />
                    )}
                    {field.help && <small>{field.help}</small>}
                  </label>
                );
              })}
            </div>
            <div className="form-actions">
              <Button variant="secondary" onClick={closeForm} type="button">Cancel</Button>
              <Button variant="primary" disabled={saving} type="submit">
                {saving ? "Saving…" : editingId ? "Save changes" : "Create"}
              </Button>
            </div>
          </form>
        </section>
      )}

      <DataTable label={`${title} list`} columns={columns} rows={records} related={relatedById} loading={loading} error={error} onRefresh={load} empty={`No ${title.toLowerCase()} yet.`} actions={showActions ? (record, _related, index) => (
                      <div className="row-actions">
                        {reorderable && capabilityAllows(canEdit, record) && <>
                          <button className="icon-button" type="button" disabled={saving || loading || index === 0} aria-label={`Move ${record.name} up`} onClick={() => move(record, "up")}><NavigationIcon name="arrow-up" /></button>
                          <button className="icon-button" type="button" disabled={saving || loading || index === records.length - 1} aria-label={`Move ${record.name} down`} onClick={() => move(record, "down")}><NavigationIcon name="arrow-down" /></button>
                        </> }
                        {capabilityAllows(canEdit, record) && (
                          <button className="text-button" onClick={() => openEdit(record)} type="button">
                            Edit
                          </button>
                        )}
                        {capabilityAllows(canDelete, record) ? (
                          <button className="text-button text-danger" onClick={() => remove(record)} type="button">
                            Delete
                          </button>
                        ) : typeof canDelete === "function" && deleteReason ? (
                          <button
                            className="text-button text-danger"
                            disabled
                            title={hookValue(deleteReason, record, "This record cannot be deleted.")}
                            type="button"
                          >
                            Delete
                          </button>
                        ) : null}
                      </div>
      ) : undefined} />
    </>
  );
}
