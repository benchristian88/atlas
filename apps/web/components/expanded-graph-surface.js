"use client";

import { useLayoutEffect, useRef } from "react";
import { NavigationIcon } from "./navigation-icon.mjs";

// Keep one mounted graph/inspector tree. A native modal promotes that same tree
// into the top layer and makes the application beneath it inert.
export function ExpandedGraphSurface({ expanded, onClose, returnFocus, scrollPosition, children, title = "Knowledge Graph" }) {
  const dialog = useRef(null);
  const closeButton = useRef(null);
  const restoreScroll = useRef(null);
  useLayoutEffect(() => {
    const element = dialog.current;
    if (!expanded) {
      const active = document.activeElement;
      element.show();
      if (restoreScroll.current) {
        window.scrollTo({ ...restoreScroll.current, behavior: "instant" });
        returnFocus.current?.focus({ preventScroll: true });
        restoreScroll.current = null;
      } else active?.focus({ preventScroll: true });
      return () => element.close();
    }
    const body = document.body;
    const root = document.documentElement;
    const { left: scrollX, top: scrollY } = scrollPosition.current;
    const previous = { position: body.style.position, top: body.style.top, left: body.style.left, width: body.style.width, overflow: root.style.overflow };
    body.style.position = "fixed";
    body.style.top = `${-scrollY}px`;
    body.style.left = `${-scrollX}px`;
    body.style.width = "100%";
    root.style.overflow = "hidden";
    element.showModal();
    closeButton.current.focus({ preventScroll: true });
    return () => {
      element.close();
      Object.assign(body.style, { position: previous.position, top: previous.top, left: previous.left, width: previous.width });
      root.style.overflow = previous.overflow;
      restoreScroll.current = { left: scrollX, top: scrollY };
      window.scrollTo({ ...restoreScroll.current, behavior: "instant" });
      returnFocus.current?.focus({ preventScroll: true });
    };
  }, [expanded, returnFocus, scrollPosition]);

  return <dialog ref={dialog} className={`knowledge-graph-surface ${expanded ? "is-expanded" : "is-embedded"}`}
    role={expanded ? "dialog" : "region"} aria-modal={expanded ? true : undefined} aria-label={title}
    onCancel={(event) => { event.preventDefault(); onClose(); }}
    onKeyDown={(event) => {
      if (!expanded || event.key !== "Tab") return;
      const controls = [...event.currentTarget.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex="0"]')].filter((el) => el.checkVisibility());
      const first = controls[0], last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}>
    <div className="expanded-graph-heading" hidden={!expanded}>
      <h2>{title}</h2>
      <button ref={closeButton} className="button button-secondary graph-icon-button" type="button" aria-label={`Close expanded ${title}`} title={`Close expanded ${title}`} onClick={onClose}><NavigationIcon name="close" /></button>
    </div>
    {children}
  </dialog>;
}
