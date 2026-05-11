import { toast } from "sonner";
import { AppNotification } from "@/types/models";

const shownDesktop = new Set<string>();
const shownToast = new Set<string>();

export async function requestDesktopPermission(): Promise<NotificationPermission> {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return "denied";
  }
  const perm = await Notification.requestPermission();
  return perm;
}

export function showDesktopNotification(n: AppNotification): void {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  if (shownDesktop.has(n.id)) return;

  try {
    const notif = new Notification(n.title, {
      body: n.body,
      tag: n.id,
      data: { packetId: n.packetId, peerId: n.peerId },
    });

    shownDesktop.add(n.id);

    notif.onclick = () => {
      try {
        window.focus();
      } catch {}
    };
  } catch (e) {
    console.warn("Desktop notification failed:", e);
  }
}

export function showToastNotification(n: AppNotification): void {
  if (shownToast.has(n.id)) return;
  shownToast.add(n.id);
  toast(n.title + " — " + n.body, { description: undefined });
}

export function clearShownCaches(): void {
  shownDesktop.clear();
  shownToast.clear();
}
