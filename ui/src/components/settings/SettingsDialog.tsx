"use client";
import React, { useEffect, useRef } from "react";
import AppearanceSettings from "./AppearanceSettings";
import NotificationSettings from "./NotificationSettings";
import ConnectionSettings from "./ConnectionSettings";
import ProfileSettings from "./ProfileSettings";
import { useTheme } from "@/hooks/useTheme";
import GlobalModal from "@/components/ui/GlobalModal";

export default function SettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  useTheme();
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <GlobalModal open={open} onClose={onClose} title="Cài đặt" size="xl">
      <div className="w-full">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-5">
          <h3 className="text-lg font-semibold">Cài đặt</h3>
          <button
            ref={closeRef}
            onClick={onClose}
            className="rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-1.5 text-sm hover:bg-white/[0.08]"
          >
            Đóng
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2">
          <div className="border-b border-white/10 md:border-b-0 md:border-r md:border-white/10">
            <AppearanceSettings />
            <NotificationSettings />
          </div>
          <div>
            <ProfileSettings />
            <ConnectionSettings />
          </div>
        </div>
      </div>
    </GlobalModal>
  );
}
