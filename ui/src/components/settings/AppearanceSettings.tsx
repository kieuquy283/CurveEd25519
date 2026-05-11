"use client";
import React from "react";
import { useSettingsStore } from "@/store/useSettingsStore";

export default function AppearanceSettings() {
  const prefs = useSettingsStore((s) => s.prefs);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const setPrefs = useSettingsStore((s) => s.setPrefs);

  return (
    <div className="p-3">
      <h4 className="font-semibold mb-2">Appearance</h4>
      <div className="flex flex-col gap-2">
        <label className="text-sm">Theme</label>
        <select value={prefs.theme} onChange={(e) => setTheme(e.target.value as "dark" | "light" | "system")} className="bg-slate-800 rounded-md px-2 py-1">
          <option value="dark">Dark</option>
          <option value="light">Light</option>
          <option value="system">System</option>
        </select>

        <label className="text-sm">Font Size</label>
        <select value={prefs.fontSize} onChange={(e) => setPrefs({ fontSize: e.target.value as "sm" | "md" | "lg" })} className="bg-slate-800 rounded-md px-2 py-1">
          <option value="sm">Small</option>
          <option value="md">Medium</option>
          <option value="lg">Large</option>
        </select>

        <label className="flex items-center gap-2">
          <input type="checkbox" checked={prefs.compactMode} onChange={(e) => setPrefs({ compactMode: e.target.checked })} />
          <span className="text-sm">Compact mode</span>
        </label>
      </div>
    </div>
  );
}
