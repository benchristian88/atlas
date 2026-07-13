"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiRequest } from "../lib/api";
import { PageHeader } from "./page-header";

const EMPTY_DEPENDENCIES = [];

function valueForInput(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

export function CrudScreen({
  eyebrow,
  title,
  description,
  endpoint,
  fields,
  columns,
  emptyValues,
  dependencies = EMPTY_DEPENDENCIES,
  preparePayload = (form) => form,
}) {
  const [records, setRecords] = useState([]);
  const [related, setRelated] = useState({});
  const [form, setForm] = useState(emptyValues);
  const [editingId, setEditingId] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const initialLoadStarted = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [items, ...relatedResults] = await Promise.all([
        apiRequest(endpoint),
        ...dependencies.map((dependency) => apiRequest(dependency.endpoint)),
      ]);
      setRecords(items);
      setRelated(
        Object.fromEntries(dependencies.map((dependency, index) => [dependency.key, relatedResults[index]])),
      );
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [endpoint, dependencies]);

  useEffect(() => {
    if (initialLoadStarted.current) return;
    initialLoadStarted.current = true;
    load();
  }, [load]);

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
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(record) {
    if (!window.confirm(`Delete “${record.name}”? This cannot be undone.`)) return;
    setError("");
    try {
      await apiRequest(`${endpoint}/${record.id}`, { method: "DELETE" });
      await load();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  return (
    <>
      <div className="page-heading-row">
        <PageHeader eyebrow={eyebrow} title={title} description={description} />
        <button className="button button-primary" onClick={openCreate} type="button">Add {title.replace(/s$/, "")}</button>
      </div>

      {error && <div className="error-banner" role="alert">{error}</div>}

      {formOpen && (
        <section className="form-card">
          <div className="form-card-header">
            <h2>{editingId ? `Edit ${title.replace(/s$/, "")}` : `Add ${title.replace(/s$/, "")}`}</h2>
            <button className="icon-button" onClick={closeForm} type="button" aria-label="Close form">×</button>
          </div>
          <form className="resource-form" onSubmit={submit}>
            <div className="form-grid">
              {fields.map((field) => {
                const unfilteredOptions = field.optionsKey ? related[field.optionsKey] || [] : field.options || [];
                const options = field.optionsFilter
                  ? unfilteredOptions.filter((option) => field.optionsFilter(option, form))
                  : unfilteredOptions;
                return (
                  <label className={field.wide ? "field field-wide" : "field"} key={field.name}>
                    <span>{field.label}{field.required ? " *" : ""}</span>
                    {field.type === "textarea" ? (
                      <textarea
                        name={field.name}
                        disabled={field.createOnly && Boolean(editingId)}
                        onChange={(event) => setForm({ ...form, [field.name]: event.target.value })}
                        required={field.required}
                        rows={field.rows || 3}
                        value={form[field.name]}
                      />
                    ) : field.type === "select" ? (
                      <select
                        name={field.name}
                        disabled={field.createOnly && Boolean(editingId)}
                        onChange={(event) => setForm({
                          ...form,
                          [field.name]: event.target.value,
                          ...Object.fromEntries((field.clearFields || []).map((name) => [name, ""])),
                        })}
                        required={field.required}
                        value={form[field.name]}
                      >
                        {!field.required && <option value="">None</option>}
                        {field.placeholder && <option value="">{field.placeholder}</option>}
                        {form[field.name] && !options.some((option) => (option.id ?? option.value) === form[field.name]) && (
                          <option value={form[field.name]}>{form[field.name]} (existing custom value)</option>
                        )}
                        {options.map((option) => (
                          <option key={option.id ?? option.value} value={option.id ?? option.value}>
                            {field.optionLabel ? field.optionLabel(option, relatedById) : option.name ?? option.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        name={field.name}
                        disabled={field.createOnly && Boolean(editingId)}
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
              <button className="button button-secondary" onClick={closeForm} type="button">Cancel</button>
              <button className="button button-primary" disabled={saving} type="submit">
                {saving ? "Saving…" : editingId ? "Save changes" : "Create"}
              </button>
            </div>
          </form>
        </section>
      )}

      <section className="table-card" aria-label={`${title} list`}>
        <div className="table-meta">
          <span>{loading ? "Loading…" : `${records.length} records`}</span>
          <button className="text-button" disabled={loading} onClick={load} type="button">Refresh</button>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}<th>Actions</th></tr></thead>
            <tbody>
              {!loading && records.length === 0 && (
                <tr><td className="empty-state" colSpan={columns.length + 1}>No {title.toLowerCase()} yet.</td></tr>
              )}
              {records.map((record) => (
                <tr key={record.id}>
                  {columns.map((column) => (
                    <td key={column.key}>{column.render ? column.render(record, relatedById) : record[column.key] || "—"}</td>
                  ))}
                  <td>
                    <div className="row-actions">
                      <button className="text-button" onClick={() => openEdit(record)} type="button">Edit</button>
                      <button className="text-button text-danger" onClick={() => remove(record)} type="button">Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
