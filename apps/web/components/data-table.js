import { Button } from "./button";

export function DataTable({ columns, rows = [], label, loading = false, error, onRefresh, empty = "No records yet.", related = {}, actions, caption = label }) {
  const resolved = actions ? [...columns, { key: "actions", label: "Actions", render: actions }] : columns;
  return <section className="table-card" aria-label={label} aria-busy={loading}>
    <div className="table-meta"><span role="status">{loading ? "Loading…" : error ? "Records could not be loaded." : `${rows.length} records`}</span>{onRefresh && <Button variant="quiet" disabled={loading} onClick={onRefresh}>Refresh</Button>}</div>
    <div className="table-scroll" role="region" aria-label={`${label} table`} tabIndex={0}>
      <table><caption className="sr-only">{caption}</caption><thead><tr>{resolved.map(column => <th scope="col" key={column.key} >{column.label}</th>)}</tr></thead>
        <tbody>{!rows.length && <tr><td className="empty-state" colSpan={resolved.length}>{loading ? "Loading…" : error ? <span role="alert">{error}</span> : empty}</td></tr>}{rows.map((row, index) => <tr key={row.id}>{resolved.map(column => <td key={column.key}>{column.render ? column.render(row, related, index) : row[column.key] ?? "—"}</td>)}</tr>)}</tbody>
      </table>
    </div>
  </section>;
}
