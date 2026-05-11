"use client";
import React from "react";
import { useNotificationStore } from "@/store/useNotificationStore";
import NotificationItem from "./NotificationItem";

export default function NotificationCenter() {
  const getRecent = useNotificationStore((s) => s.getRecentNotifications);
  const notifs = getRecent(50);
  const unread = useNotificationStore((s) => s.getUnreadCount());

  return (
    <div className="w-80 bg-slate-900 border border-slate-800 rounded-md p-2">
      <div className="flex items-center justify-between px-2 py-1">
        <div className="font-semibold">Notifications</div>
        <div className="text-sm text-slate-400">{unread} unread</div>
      </div>
      <div className="mt-2 flex flex-col gap-2 max-h-96 overflow-auto">
        {notifs.length === 0 ? (
          <div className="p-3 text-slate-500">No notifications</div>
        ) : (
          notifs.map((n) => <NotificationItem key={n.id} n={n} />)
        )}
      </div>
    </div>
  );
}
