import { Children, isValidElement, Fragment } from "react";

export function PageHeader({ eyebrow, title, description, actions, metadata, identity, variant = "standard" }) {
  const hasActions = content => Children.toArray(content).some(child => isValidElement(child) && child.type === Fragment ? hasActions(child.props.children) : Boolean(child));
  return <header className={`page-header${variant === "canvas" ? " page-header-canvas" : ""}`}>
    <div className="page-header-main">
      {identity}
      <div className="page-header-copy">{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p className="page-description">{description}</p>}{metadata && <div className="page-header-metadata">{metadata}</div>}</div>
      {hasActions(actions) && <div className="page-header-actions">{actions}</div>}
    </div>
  </header>;
}
