"use client";
import React, { useEffect } from "react";
import AppearanceSettings from "./AppearanceSettings";
import NotificationSettings from "./NotificationSettings";
import ConnectionSettings from "./ConnectionSettings";
import ProfileSettings from "./ProfileSettings";
import { useTheme } from "@/hooks/useTheme";

export default function SettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  useTheme();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    if (open) {
      window.addEventListener("keydown", onKey);
      const first = document.querySelector("[data-settings-first]") as HTMLElement | null;
      first?.focus();
    }
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div role="dialog" aria-modal="true" aria-label="Settings" className="fixed inset-0 flex items-center justify-center bg-black/60 z-50">
      <div className="bg-slate-900 w-full max-w-3xl rounded-md overflow-hidden" tabIndex={-1}>
        <div className="flex">
          <div className="w-1/2 border-r border-slate-800">
            <AppearanceSettings />
            <NotificationSettings />
          </div>
          <div className="w-1/2">
            <ProfileSettings />
            <ConnectionSettings />
          </div>
        </div>
        <div className="flex justify-end p-3 border-t border-slate-800">
          <button data-settings-first onClick={onClose} className="px-3 py-2 rounded-md">Close</button>
        </div>
      </div>
    </div>
  );
}
