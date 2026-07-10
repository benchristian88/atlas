export function DataTable({ columns, rows, label }) {
  return (
    <section className="table-card" aria-label={label}>
      <div className="table-meta">
        <span>{rows.length} records</span>
        <span>Sample data</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                {columns.map((column) => <td key={column.key}>{column.render ? column.render(row) : row[column.key]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
