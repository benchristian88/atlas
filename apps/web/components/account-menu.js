"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { primaryRoleLabel } from "../lib/user-presentation.mjs";
import { UserAvatar } from "./user-avatar";

function menuItems(menu) {
  return [...(menu?.querySelectorAll('[role="menuitem"]') || [])];
}

export function AccountMenu({ user, onLogout, signingOut = false }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  const displayName = user.display_name || user.email || "Atlas user";
  const role = primaryRoleLabel(user);
  const imageUrl = user.avatar_url || user.image_url || user.profile_image_url || null;

  useEffect(() => {
    if (!open) return undefined;
    function handlePointerDown(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    }
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  function focusMenuItem(position) {
    const items = menuItems(menuRef.current);
    if (!items.length) return;
    const activeIndex = items.indexOf(document.activeElement);
    if (position === "first") items[0].focus();
    else if (position === "last") items.at(-1).focus();
    else if (position === "next") items[(activeIndex + 1 + items.length) % items.length].focus();
    else items[(activeIndex - 1 + items.length) % items.length].focus();
  }

  function handleTriggerKeyDown(event) {
    if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
    event.preventDefault();
    setOpen(true);
    requestAnimationFrame(() => focusMenuItem(event.key === "ArrowDown" ? "first" : "last"));
  }

  function handleMenuKeyDown(event) {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "Home") focusMenuItem("first");
    else if (event.key === "End") focusMenuItem("last");
    else focusMenuItem(event.key === "ArrowDown" ? "next" : "previous");
  }

  return <div className="account-menu" ref={rootRef}>
    <button aria-controls="atlas-user-menu" aria-expanded={open} aria-haspopup="menu" aria-label={`Open user menu for ${displayName}`} className="account-menu-trigger" disabled={signingOut} onClick={() => setOpen((current) => !current)} onKeyDown={handleTriggerKeyDown} ref={triggerRef} type="button">
      <UserAvatar displayName={displayName} imageUrl={imageUrl} />
      <span className="account-trigger-copy"><strong>{displayName}</strong><span>{role}</span></span>
      <span aria-hidden="true" className={`account-menu-chevron${open ? " open" : ""}`}>⌄</span>
    </button>
    {open && <div aria-label="User account" className="account-dropdown" id="atlas-user-menu" onKeyDown={handleMenuKeyDown} ref={menuRef} role="menu">
      <Link className="account-dropdown-item" href="/profile" onClick={() => setOpen(false)} role="menuitem">My profile</Link>
      <div className="account-dropdown-separator" role="separator" />
      <button className="account-dropdown-item account-dropdown-logout" disabled={signingOut} onClick={async () => { setOpen(false); await onLogout(); }} role="menuitem" type="button">{signingOut ? "Logging out…" : "Log out"}</button>
    </div>}
  </div>;
}
