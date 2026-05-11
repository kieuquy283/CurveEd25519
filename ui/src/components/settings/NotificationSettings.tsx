"use client";
import React from "react";
import { useSettingsStore } from "@/store/useSettingsStore";

export default function NotificationSettings() {
  const prefs = useSettingsStore((s) => s.prefs);
  const setPrefs = useSettingsStore((s) => s.setPrefs);

  return (
    <div className="p-3">
      <h4 className="font-semibold mb-2">Notifications</h4>
      <div className="flex flex-col gap-2">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={prefs.enableSound} onChange={(e) => setPrefs({ enableSound: e.target.checked })} />
          <span className="text-sm">Enable sound</span>
        </label>

        <label className="flex items-center gap-2">
          <input type="checkbox" checked={prefs.enableDesktopNotifications} onChange={(e) => setPrefs({ enableDesktopNotifications: e.target.checked })} />
          <span className="text-sm">Desktop notifications</span>
        </label>

        <label className="flex items-center gap-2">
          <input type="checkbox" checked={prefs.enableTypingIndicators} onChange={(e) => setPrefs({ enableTypingIndicators: e.target.checked })} />
          <span className="text-sm">Typing indicators</span>
        </label>

        <label className="flex items-center gap-2">
          <input type="checkbox" checked={prefs.enableReadReceipts} onChange={(e) => setPrefs({ enableReadReceipts: e.target.checked })} />
          <span className="text-sm">Read receipts</span>
        </label>
      </div>
    </div>
  );
}
