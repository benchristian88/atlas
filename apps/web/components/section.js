export function Surface({ children, className = "", ...props }) {
  return <div {...props} className={`surface ${className}`.trim()}>{children}</div>;
}
export function Section({ title, description, actions, children, id, className = "" }) {
  return <section id={id} className={`section ${className}`.trim()}><header className="ops-section-header"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{actions}</header>{children}</section>;
}
export function EmptyState({ children, title, description, action }) {
  return <div className="empty-state">{title && <strong>{title}</strong>}{description && <p>{description}</p>}{children}{action}</div>;
}
