import Link from "next/link";
import { NavigationIcon } from "./navigation-icon.mjs";

export function Button({ children, variant = "secondary", loading = false, disabled = false, href, className = "", type = "button", ...props }) {
  const classes = `button button-${variant} ${className}`.trim();
  const blocked = disabled || loading;
  if (href) return <Link {...props} href={href} className={classes} aria-disabled={blocked || undefined} aria-busy={loading || undefined} tabIndex={blocked ? -1 : undefined} onClick={event => { if (blocked) event.preventDefault(); else props.onClick?.(event); }}>{children}</Link>;
  return <button {...props} type={type} className={classes} disabled={blocked} aria-busy={loading || undefined}>{children}</button>;
}

export function IconButton({ label, icon, children, className = "", ...props }) {
  if (!label) throw new Error("IconButton requires an accessible label");
  return <Button {...props} className={`icon-button ${className}`} aria-label={label} title={label}>{icon ? <NavigationIcon name={icon} /> : children}</Button>;
}
