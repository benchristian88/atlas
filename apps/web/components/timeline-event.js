export function TimelineEvent({ children, className = "" }) {
  return <article className={`timeline-event ${className}`.trim()}><div className="timeline-marker" aria-hidden="true" /><div className="timeline-event-content">{children}</div></article>;
}
