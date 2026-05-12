"use client";
import React from "react";
import { useSettingsStore } from "@/store/useSettingsStore";

export default function AppearanceSettings() {
  const prefs = useSettingsStore((s) => s.prefs);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const setPrefs = useSettingsStore((s) => s.setPrefs);

  return (
    <div className="p-3">
      <h4 className="font-semibold mb-2">Giao diện</h4>
      <div className="flex flex-col gap-2">
        <label className="text-sm">Chế độ màu</label>
        <select value={prefs.theme} onChange={(e) => setTheme(e.target.value as "dark" | "light" | "system")} className="bg-slate-800 rounded-md px-2 py-1">
          <option value="dark">Tối</option>
          <option value="light">Sáng</option>
          <option value="system">Theo hệ thống</option>
        </select>

        <label className="text-sm">Cỡ chữ</label>
        <select value={prefs.fontSize} onChange={(e) => setPrefs({ fontSize: e.target.value as "sm" | "md" | "lg" })} className="bg-slate-800 rounded-md px-2 py-1">
          <option value="sm">Nhỏ</option>
          <option value="md">Vừa</option>
          <option value="lg">Lớn</option>
        </select>

        <label className="text-sm">Phông chữ</label>
        <select
          value={prefs.fontFamily}
          onChange={(e) =>
            setPrefs({
              fontFamily: e.target.value as "default" | "sans" | "serif" | "mono",
            })
          }
          className="bg-slate-800 rounded-md px-2 py-1"
        >
          <option value="default">Mặc định</option>
          <option value="sans">Sans</option>
          <option value="serif">Serif</option>
          <option value="mono">Mono</option>
        </select>

        <label className="flex items-center gap-2">
          <input type="checkbox" checked={prefs.compactMode} onChange={(e) => setPrefs({ compactMode: e.target.checked })} />
          <span className="text-sm">Chế độ gọn</span>
        </label>
      </div>
    </div>
  );
}
