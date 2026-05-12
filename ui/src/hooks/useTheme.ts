"use client";
import { useEffect } from "react";
import { useSettingsStore } from "@/store/useSettingsStore";

export function useTheme() {
  const theme = useSettingsStore((s) => s.prefs.theme);
  const fontFamily = useSettingsStore((s) => s.prefs.fontFamily);

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

  useEffect(() => {
    if (typeof document === "undefined") return;
    const body = document.body;
    body.classList.remove("font-pref-default", "font-pref-sans", "font-pref-serif", "font-pref-mono");
    if (fontFamily === "sans") body.classList.add("font-pref-sans");
    else if (fontFamily === "serif") body.classList.add("font-pref-serif");
    else if (fontFamily === "mono") body.classList.add("font-pref-mono");
    else body.classList.add("font-pref-default");
  }, [fontFamily]);
}
