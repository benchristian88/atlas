"use client";

import { useCallback, useEffect, useState } from "react";
import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { PageHeader } from "../../../components/page-header";
import { useWorkspaceContext } from "../../../components/workspace-context";
import { apiRequest } from "../../../lib/api";

function blankAssignment(roles) {
  return { role_id: roles.find((role) => role.active)?.id || "", scope_type: "global", customer_id: "", site_id: "" };
}

function assignmentsPayload(assignments) {
  return assignments.map((assignment) => ({
    role_id: assignment.role_id,
    scope_type: assignment.scope_type,
    customer_id: assignment.scope_type === "global" ? null : assignment.customer_id,
    site_id: assignment.scope_type === "site" ? assignment.site_id : null,
  }));
}

function formatDate(value) {
  if (!value) return "Never";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function UsersAdminPage() {
  const { hasGlobalPermission, hasPermission } = useAuth();
  const { customers, sites } = useWorkspaceContext();
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [form, setForm] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [resetUser, setResetUser] = useState(null);
  const [resetPassword, setResetPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const canView = hasGlobalPermission("users.view");
  const canEdit = hasGlobalPermission("users.edit");
  const canDisable = hasGlobalPermission("users.disable");
  const canAssign = hasGlobalPermission("users.assign_roles")
    && hasGlobalPermission("roles.view");
  const canCreate = hasGlobalPermission("users.create") && canAssign;

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError("");
    try {
      const [userRecords, roleRecords] = await Promise.all([
        apiRequest("/users"),
        hasGlobalPermission("roles.view") ? apiRequest("/roles") : Promise.resolve([]),
      ]);
      setUsers(userRecords);
      setRoles(roleRecords);
    } catch (requestError) {
      setError(requestError.message || "Atlas could not load users.");
    } finally {
      setLoading(false);
    }
  }, [canView, hasGlobalPermission]);

  useEffect(() => { load(); }, [load]);

  if (!canView) return <AccessDenied />;

  function openCreate() {
    setEditingId(null);
    setForm({
      email: "",
      display_name: "",
      temporary_password: "",
      is_active: true,
      force_password_change: true,
      assignments: [blankAssignment(roles)],
    });
    setError("");
    setSuccess("");
  }

  function openEdit(user) {
    setEditingId(user.id);
    setForm({
      email: user.email,
      display_name: user.display_name,
      temporary_password: "",
      is_active: user.is_active,
      force_password_change: user.force_password_change,
      assignments: user.assignments.map((assignment) => ({
        role_id: assignment.role_id,
        scope_type: assignment.scope_type,
        customer_id: assignment.customer_id || "",
        site_id: assignment.site_id || "",
      })),
    });
    setError("");
    setSuccess("");
  }

  function updateAssignment(index, changes) {
    setForm((current) => ({
      ...current,
      assignments: current.assignments.map((assignment, assignmentIndex) => (
        assignmentIndex === index ? { ...assignment, ...changes } : assignment
      )),
    }));
  }

  async function saveUser(event) {
    event.preventDefault();
    if (!form.assignments.length) {
      setError("Add at least one role and scope assignment.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      if (editingId) {
        const payload = {
          display_name: form.display_name,
          force_password_change: form.force_password_change,
          ...(canDisable ? { is_active: form.is_active } : {}),
          ...(canAssign ? { assignments: assignmentsPayload(form.assignments) } : {}),
        };
        await apiRequest(`/users/${editingId}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        await apiRequest("/users", {
          method: "POST",
          body: JSON.stringify({
            email: form.email,
            display_name: form.display_name,
            temporary_password: form.temporary_password,
            force_password_change: form.force_password_change,
            assignments: assignmentsPayload(form.assignments),
          }),
        });
      }
      setForm(null);
      setEditingId(null);
      setSuccess(editingId ? "User updated." : "User created.");
      await load();
    } catch (requestError) {
      setError(requestError.message || "Atlas could not save this user.");
    } finally {
      setSaving(false);
    }
  }

  async function submitReset(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/users/${resetUser.id}/reset-password`, {
        method: "POST",
        body: JSON.stringify({ temporary_password: resetPassword, force_password_change: true }),
      });
      setSuccess(`Temporary password set for ${resetUser.email}. Existing sessions were invalidated.`);
      setResetUser(null);
      setResetPassword("");
      await load();
    } catch (requestError) {
      setError(requestError.message || "Atlas could not reset this password.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="page-heading-row">
        <PageHeader eyebrow="Administration" title="Users" description="Manage local accounts, lifecycle state, and role assignments. Passwords are never displayed." />
        {canCreate && <button className="button button-primary" onClick={openCreate} type="button">Add user</button>}
      </div>
      {error && <div className="error-banner" role="alert">{error}</div>}
      {success && <div className="success-banner" role="status">{success}</div>}

      {form && (
        <section className="form-card">
          <div className="form-card-header"><h2>{editingId ? "Edit user" : "Add user"}</h2><button className="icon-button" aria-label="Close form" onClick={() => setForm(null)} type="button">×</button></div>
          <form onSubmit={saveUser}>
            <div className="form-grid">
              <label className="field"><span>Email *</span><input autoComplete="off" disabled={Boolean(editingId)} onChange={(event) => setForm({ ...form, email: event.target.value })} required type="email" value={form.email} /></label>
              <label className="field"><span>Display name *</span><input onChange={(event) => setForm({ ...form, display_name: event.target.value })} required value={form.display_name} /></label>
              {!editingId && <label className="field"><span>Temporary password *</span><input autoComplete="new-password" minLength={12} onChange={(event) => setForm({ ...form, temporary_password: event.target.value })} required type="password" value={form.temporary_password} /><small>At least 12 characters.</small></label>}
              {canDisable && <label className="field checkbox-field"><input checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} type="checkbox" /><span>Account is active</span></label>}
              <label className="field checkbox-field"><input checked={form.force_password_change} onChange={(event) => setForm({ ...form, force_password_change: event.target.checked })} type="checkbox" /><span>Require password change</span></label>
            </div>

            {canAssign && <fieldset className="assignment-editor"><legend>Role and scope assignments</legend>
              {form.assignments.map((assignment, index) => {
                const availableSites = sites.filter((site) => site.customer_id === assignment.customer_id);
                return <div className="assignment-editor-row" key={`${index}-${assignment.role_id}`}>
                  <label className="field"><span>Role</span><select required value={assignment.role_id} onChange={(event) => updateAssignment(index, { role_id: event.target.value })}>{roles.filter((role) => role.active || role.id === assignment.role_id).map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>
                  <label className="field"><span>Scope</span><select value={assignment.scope_type} onChange={(event) => updateAssignment(index, { scope_type: event.target.value, customer_id: "", site_id: "" })}><option value="global">Global</option><option value="customer">Customer</option><option value="site">Site</option></select></label>
                  {assignment.scope_type !== "global" && <label className="field"><span>Customer</span><select required value={assignment.customer_id} onChange={(event) => updateAssignment(index, { customer_id: event.target.value, site_id: "" })}><option value="">Select customer</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select></label>}
                  {assignment.scope_type === "site" && <label className="field"><span>Site</span><select required value={assignment.site_id} onChange={(event) => updateAssignment(index, { site_id: event.target.value })}><option value="">Select site</option>{availableSites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label>}
                  <button className="text-button text-danger" disabled={form.assignments.length === 1} onClick={() => setForm({ ...form, assignments: form.assignments.filter((_, itemIndex) => itemIndex !== index) })} type="button">Remove</button>
                </div>;
              })}
              <button className="button button-secondary" onClick={() => setForm({ ...form, assignments: [...form.assignments, blankAssignment(roles)] })} type="button">Add assignment</button>
            </fieldset>}
            <div className="form-actions"><button className="button button-secondary" onClick={() => setForm(null)} type="button">Cancel</button><button className="button button-primary" disabled={saving} type="submit">{saving ? "Saving…" : editingId ? "Save user" : "Create user"}</button></div>
          </form>
        </section>
      )}

      {resetUser && <section className="form-card"><div className="form-card-header"><div><h2>Reset password</h2><p className="secondary-text">Set a temporary password for {resetUser.email}. All existing sessions will be invalidated.</p></div><button className="icon-button" aria-label="Close reset form" onClick={() => setResetUser(null)} type="button">×</button></div><form onSubmit={submitReset}><label className="field"><span>Temporary password</span><input autoComplete="new-password" minLength={12} onChange={(event) => setResetPassword(event.target.value)} required type="password" value={resetPassword} /></label><div className="form-actions"><button className="button button-secondary" onClick={() => setResetUser(null)} type="button">Cancel</button><button className="button button-primary" disabled={saving} type="submit">Set temporary password</button></div></form></section>}

      <section className="table-card" aria-label="Users list">
        <div className="table-meta"><span>{loading ? "Loading…" : `${users.length} users`}</span><button className="text-button" disabled={loading} onClick={load} type="button">Refresh</button></div>
        <div className="table-scroll"><table><thead><tr><th>User</th><th>Roles</th><th>Scope</th><th>State</th><th>Last login</th>{canEdit && <th>Actions</th>}</tr></thead><tbody>
          {!loading && users.length === 0 && <tr><td className="empty-state" colSpan={canEdit ? 6 : 5}>No users found.</td></tr>}
          {users.map((user) => <tr key={user.id}><td><strong>{user.display_name}</strong><br /><span className="secondary-text">{user.email}</span></td><td>{user.roles.join(", ") || "—"}</td><td>{user.assignments.map((assignment) => assignment.scope_type === "global" ? "Global" : assignment.scope_type === "customer" ? customers.find((item) => item.id === assignment.customer_id)?.name || "Customer" : sites.find((item) => item.id === assignment.site_id)?.name || "Site").join(", ")}</td><td>{user.is_active ? "Active" : "Disabled"}{user.force_password_change ? " · Password change required" : ""}</td><td>{formatDate(user.last_login_at)}</td>{canEdit && <td><div className="row-actions"><button className="text-button" onClick={() => openEdit(user)} type="button">Edit</button><button className="text-button" onClick={() => { setResetUser(user); setResetPassword(""); }} type="button">Reset password</button></div></td>}</tr>)}
        </tbody></table></div>
      </section>
    </>
  );
}
