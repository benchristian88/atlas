"use client";

import { useEffect, useState } from "react";

export function useResolvedThemeMode(preference = "system") {
  const [systemDark, setSystemDark] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setSystemDark(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return preference === "light" || preference === "dark"
    ? preference
    : systemDark ? "dark" : "light";
}
