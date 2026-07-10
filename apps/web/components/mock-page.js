import { DataTable } from "./data-table";
import { PageHeader } from "./page-header";

export function MockPage({ eyebrow, title, description, columns, rows }) {
  return (
    <>
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <div className="mock-notice">
        <span className="notice-dot" aria-hidden="true" />
        This page uses sample data until its API endpoint is available.
      </div>
      <DataTable columns={columns} rows={rows} label={`${title} list`} />
    </>
  );
}
