"use client";
import { useEffect } from "react";
import { useSettingsStore } from "@/store/useSettingsStore";

export function useTheme() {
  const theme = useSettingsStore((s) => s.prefs.theme);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    // remove any of dark/light classes then apply
    if (theme === "dark") {
      root.classList.add("dark");
    } else if (theme === "light") {
      root.classList.remove("dark");
    } else {
      // system - follow prefers-color-scheme
      const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      if (prefersDark) root.classList.add("dark"); else root.classList.remove("dark");
    }
  }, [theme]);
}
