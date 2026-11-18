"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { apiRequest } from "../lib/api";
import { useAuth } from "./auth-context";

const BuildInfoContext = createContext(null);

export function BuildInfoProvider({ children }) {
  const { hasGlobalPermission, user } = useAuth();
  const canRead = !user.force_password_change && hasGlobalPermission("system_settings.manage");
  const [buildInfo, setBuildInfo] = useState(null);
  const request = useRef(null);

  useEffect(() => {
    if (!canRead) {
      request.current = null;
      setBuildInfo(null);
      return;
    }

    // Share the optional read across routes, including when metadata is unavailable.
    request.current ??= apiRequest("/system-settings/build-info", {
      cache: "no-store",
      omitContext: true,
      redirectOnUnauthorized: false,
    }).catch(() => null);
    let active = true;
    request.current.then((metadata) => {
      if (active && typeof metadata?.version === "string" && metadata.version.trim()) {
        setBuildInfo(metadata);
      }
    });
    return () => { active = false; };
  }, [canRead]);

  return <BuildInfoContext.Provider value={canRead ? buildInfo : null}>{children}</BuildInfoContext.Provider>;
}

export function useBuildInfo() {
  return useContext(BuildInfoContext);
}
