export function FilterToolbar({ actions, children, className = "", gridClassName = "", onSubmit }) {
  const classes = ["filter-toolbar", className].filter(Boolean).join(" ");
  const gridClasses = ["filter-toolbar-grid", gridClassName].filter(Boolean).join(" ");

  return (
    <form className={classes} onSubmit={onSubmit}>
      <div className={gridClasses}>{children}</div>
      {actions && <div className="filter-toolbar-actions">{actions}</div>}
    </form>
  );
}
