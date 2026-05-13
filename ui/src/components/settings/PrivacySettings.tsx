"use client";

import React from "react";
import { useSettingsStore } from "@/store/useSettingsStore";

export default function PrivacySettings() {
  const prefs = useSettingsStore((s) => s.prefs);
  const setPrefs = useSettingsStore((s) => s.setPrefs);

  const setAutoHideMs = (value: number) => setPrefs({ autoHideMs: value });

  return (
    <div className="p-3 space-y-3">
      <h4 className="font-semibold">Privacy & leak protection</h4>
      <p className="text-xs text-zinc-400">
        Privacy Mode reduces accidental leaks. It cannot prevent screenshots, screen recording, DevTools, or photos taken with another device.
      </p>

      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 space-y-2">
        <label className="flex items-center justify-between gap-2 text-sm">
          <span>Chế độ riêng tư</span>
          <input type="checkbox" checked={prefs.privacyMode} onChange={(e) => setPrefs({ privacyMode: e.target.checked })} />
        </label>
        <label className="flex items-center justify-between gap-2 text-sm">
          <span>Watermark động</span>
          <input type="checkbox" checked={prefs.watermarkEnabled} onChange={(e) => setPrefs({ watermarkEnabled: e.target.checked })} />
        </label>
        <label className="flex items-center justify-between gap-2 text-sm">
          <span>Làm mờ tin nhắn</span>
          <input type="checkbox" checked={prefs.blurMessages} onChange={(e) => setPrefs({ blurMessages: e.target.checked })} />
        </label>
        <label className="flex items-center justify-between gap-2 text-sm">
          <span>Ẩn khi rời khỏi tab</span>
          <input type="checkbox" checked={prefs.hideOnWindowBlur} onChange={(e) => setPrefs({ hideOnWindowBlur: e.target.checked })} />
        </label>
        <label className="flex items-center justify-between gap-2 text-sm">
          <span>Không sao chép nội dung rõ</span>
          <input type="checkbox" checked={prefs.disablePlaintextCopy} onChange={(e) => setPrefs({ disablePlaintextCopy: e.target.checked })} />
        </label>
        <label className="flex items-center justify-between gap-2 text-sm">
          <span>Tắt chuột phải trong tin nhắn</span>
          <input type="checkbox" checked={prefs.disableContextMenu} onChange={(e) => setPrefs({ disableContextMenu: e.target.checked })} />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block">Tự ẩn sau</span>
          <select
            value={prefs.autoHideMs}
            onChange={(e) => setAutoHideMs(Number(e.target.value))}
            className="w-full rounded-xl border border-white/10 bg-slate-900/70 px-2 py-1"
          >
            <option value={3000}>3 giây</option>
            <option value={5000}>5 giây</option>
            <option value={10000}>10 giây</option>
          </select>
        </label>
      </div>
    </div>
  );
}
