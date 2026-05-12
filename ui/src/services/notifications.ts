import { getApiBaseUrl } from "@/config/env";
import { toast } from "sonner";
import { AppNotification } from "@/types/models";

async function parseOrThrow(response: Response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${response.status}`);
  }
  return data;
}

export async function listNotifications(user: string) {
  const response = await fetch(`${getApiBaseUrl()}/api/notifications?user=${encodeURIComponent(user)}`);
  return parseOrThrow(response) as Promise<{ ok: boolean; notifications: Array<Record<string, unknown>> }>;
}

export async function markNotificationRead(id: string) {
  const response = await fetch(`${getApiBaseUrl()}/api/notifications/${encodeURIComponent(id)}/read`, {
    method: "POST",
  });
  return parseOrThrow(response);
}

export async function requestDesktopPermission(): Promise<NotificationPermission> {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return "denied";
  }
  if (Notification.permission !== "default") {
    return Notification.permission;
  }
  return Notification.requestPermission();
}

export function showDesktopNotification(notification: AppNotification) {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  try {
    new Notification(notification.title, { body: notification.body });
  } catch {
    // ignore desktop notification failure
  }
}

export function showToastNotification(notification: AppNotification) {
  const level = notification.level;
  if (level === "error") {
    toast.error(notification.title, { description: notification.body });
    return;
  }
  if (level === "warning") {
    toast.warning(notification.title, { description: notification.body });
    return;
  }
  if (level === "success") {
    toast.success(notification.title, { description: notification.body });
    return;
  }
  toast(notification.title, { description: notification.body });
}
