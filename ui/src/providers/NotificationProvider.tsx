"use client";
import React, { useEffect, useRef } from "react";
import { Toaster } from "sonner";
import { useNotificationStore } from "@/store/useNotificationStore";
import { requestDesktopPermission, showDesktopNotification, showToastNotification } from "@/services/notifications";

export default function NotificationProvider({ children }: { children: React.ReactNode }) {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    // Request permission proactively but non-blocking
    if (typeof window !== "undefined" && "Notification" in window) {
      if (Notification.permission === "default") {
        requestDesktopPermission().catch(() => {});
      }
    }

    // Subscribe to notifications and display toasts/desktop notifications
    const unsub = useNotificationStore.subscribe((state) => {
      const notifications = state.notifications;
      const last = notifications[notifications.length - 1];
      if (!last) return;
      // Show toast
      showToastNotification(last);
      // Show desktop notification if permission granted
      if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
        showDesktopNotification(last);
      }
    });

    return () => {
      unsub();
    };
  }, []);

  return (
    <>
      <Toaster position="top-right" richColors />
      {children}
    </>
  );
}
