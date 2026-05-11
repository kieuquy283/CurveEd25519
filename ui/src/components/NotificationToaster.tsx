/**
 * Notification toast component using sonner.
 */

"use client";

import React, { useEffect } from "react";
import { Toaster, toast } from "sonner";
import { useNotificationStore } from "@/store/useNotificationStore";

export function NotificationToaster() {
  const notifications = useNotificationStore((s) => s.notifications);

  useEffect(() => {
    // Show toast for latest notification
    if (notifications.length > 0) {
      const latest = notifications[notifications.length - 1];
      
      const toastFn = {
        info: toast.info,
        success: toast.success,
        warning: toast.warning,
        error: toast.error,
        message: toast.message,
        system: toast.info,
      }[latest.level] || toast.info;

      toastFn(latest.title, {
        description: latest.body,
      });
    }
  }, [notifications]);

  return (
    <Toaster
      theme="dark"
      position="bottom-right"
      richColors
      expand
      closeButton
    />
  );
}
