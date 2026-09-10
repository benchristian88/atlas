import Link from "next/link";
import { StatusBadge } from "./status-badge";

export function KnowledgeProfileTable({ requirements, entityLabel, typeId, globalScope = false, loading, canManage, onRefresh, onEdit, onToggle, onRemove }) {
  const scopeKey = entityLabel === "Asset" ? "asset_type_id" : "service_type_id";
  const groups = globalScope ? [["Global requirements", requirements]] : [
    ["Global requirements", requirements.filter((item) => !item[scopeKey])],
    ["Type-specific requirements", requirements.filter((item) => item[scopeKey])],
  ];
  const columns = canManage ? 7 : 6;
  return <section className="table-card">
    <div className="table-meta"><span>{loading ? "Loading…" : `${requirements.length} requirements`}</span><button className="text-button" onClick={onRefresh} type="button">Refresh</button></div>
    {globalScope && !loading && requirements.length === 0 ? <p className="empty-state">No global {entityLabel} requirements are configured.</p> : <div className="table-scroll" role="region" aria-label={`${entityLabel} knowledge requirements`} tabIndex={0}>
      <table className="knowledge-profile-table">
        <caption className="sr-only">{globalScope ? `Global ${entityLabel} requirements` : `${entityLabel} Type knowledge requirements, grouped by scope`}</caption>
        <thead><tr><th scope="col" className="profile-requirement-column">Requirement</th><th scope="col" className="profile-level-column">Level</th><th scope="col" className="profile-severity-column">Severity</th><th scope="col" className="profile-rule-column">Rule</th><th scope="col" className="profile-scope-column">Scope</th><th scope="col" className="profile-state-column">State</th>{canManage && <th scope="col" className="profile-actions-column">Actions</th>}</tr></thead>
        {groups.map(([label, items]) => <tbody key={label}>
          <tr className="profile-group-heading"><th scope="rowgroup" colSpan={columns}><div className="profile-group-label"><span>{label}</span>{!globalScope && label === "Global requirements" && canManage && <Link className="text-button" href={`/admin/${entityLabel.toLowerCase()}-types/requirements/global`}>Manage global requirements →</Link>}</div></th></tr>
          {!loading && items.length === 0 && <tr><td className="empty-state" colSpan={columns}>{globalScope ? `No global ${entityLabel} requirements are configured.` : `No ${label.toLowerCase()} configured.`}</td></tr>}
          {items.map((item) => <tr key={item.id}>
            <td><div className="table-cell-identity"><strong>{item.name}</strong><small className="secondary-text">{item.description || item.remediation_hint || "No description"}</small></div></td>
            <td><StatusBadge status={item.requirement_level} /></td>
            <td><StatusBadge status={item.severity} /></td>
            <td className="profile-rule secondary-text">{item.rule_summary}</td>
            <td><StatusBadge status={item[scopeKey] ? `This ${entityLabel} Type` : "Global default"} /></td>
            <td><StatusBadge status={!item.configuration_valid ? "Invalid" : item.active ? "Active" : "Inactive"} /></td>
            {canManage && <td>{(globalScope || item[scopeKey] === typeId) && <div className="row-actions">
              <button className="text-button" onClick={() => onEdit(item)} type="button">Edit</button><button className="text-button" onClick={() => onEdit(item, true)} type="button">Duplicate</button>
              <button className="text-button" onClick={() => onToggle(item)} type="button">{item.active ? "Deactivate" : "Reactivate"}</button>
              {(!globalScope || item.can_delete) && <button className="text-button text-danger" onClick={() => onRemove(item)} type="button">Delete</button>}
            </div>}</td>}
          </tr>)}
        </tbody>)}
      </table>
    </div>}
  </section>;
}
