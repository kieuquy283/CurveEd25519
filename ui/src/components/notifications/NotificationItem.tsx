"use client";
import React from "react";
import { AppNotification } from "@/types/models";
import { useNotificationStore } from "@/store/useNotificationStore";

export default function NotificationItem({ n }: { n: AppNotification }) {
  const markAsRead = useNotificationStore((s) => s.markAsRead);
  const dismiss = useNotificationStore((s) => s.dismiss);

  return (
    <div className="flex items-start gap-3 p-3 hover:bg-slate-800 rounded-md">
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <div className="font-semibold text-sm">{n.title}</div>
          <div className="text-xs text-slate-500">{new Date(n.createdAt).toLocaleTimeString()}</div>
        </div>
        <div className="text-slate-400 text-sm mt-1">{n.body}</div>
      </div>
      <div className="flex flex-col gap-2">
        <button onClick={() => markAsRead(n.id)} className="text-xs text-slate-400 hover:text-white">Read</button>
        <button onClick={() => dismiss(n.id)} className="text-xs text-slate-400 hover:text-white">Dismiss</button>
      </div>
    </div>
  );
}
