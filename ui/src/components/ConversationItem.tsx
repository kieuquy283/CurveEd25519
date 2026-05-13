/**
 * ConversationItem — a single conversation row in the sidebar.
 */

"use client";

import React from "react";
import { Conversation } from "@/types/models";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/time";

interface ConversationItemProps {
  conversation: Conversation;
  isActive: boolean;
  onSelect: () => void;
}

export function ConversationItem({
  conversation,
  isActive,
  onSelect,
}: ConversationItemProps) {
  const name = conversation.peerName ?? conversation.peerId;
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const lastMsg = conversation.lastMessage?.text ?? "";
  const lastTime = conversation.lastMessageAt
    ? formatRelativeTime(new Date(conversation.lastMessageAt))
    : "";

  const avatarColors = [
    "from-blue-500 to-cyan-400",
    "from-violet-500 to-purple-400",
    "from-pink-500 to-rose-400",
    "from-amber-500 to-orange-400",
    "from-emerald-500 to-teal-400",
    "from-indigo-500 to-blue-400",
  ];
  const colorIdx =
    name.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0) %
    avatarColors.length;
  const avatarColor = avatarColors[colorIdx];

  return (
    <button
      onClick={onSelect}
      className={cn(
        "group mx-1 flex w-full items-center gap-3 rounded-3xl px-3 py-3",
        "text-left transition-all duration-150 group",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/60",
        isActive
          ? "border border-violet-400/50 bg-gradient-to-r from-violet-600/20 to-blue-600/10 text-zinc-100 shadow-[0_0_30px_rgba(124,58,237,0.22)]"
          : "text-zinc-100 hover:bg-white/[0.06]"
      )}
    >
      {/* Avatar */}
      <div className="relative flex-shrink-0">
        <div
          className={cn(
            "h-12 w-12 rounded-full bg-gradient-to-br flex items-center justify-center",
            "text-sm font-semibold text-white shadow-sm",
            avatarColor
          )}
        >
          {initials}
        </div>
        {/* Online dot */}
        {conversation.isOnline && (
          <span
            className={cn(
              "absolute bottom-0 right-0 h-3 w-3 rounded-full bg-emerald-400 ring-2 ring-slate-950"
            )}
          />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-1 mb-0.5">
            <span className="truncate text-sm font-medium">{name}</span>
            {lastTime && (
              <span className="shrink-0 text-[10px] text-zinc-500">
                {lastTime}
              </span>
            )}
          </div>
          <div className="flex items-center justify-between gap-1">
            <p className="max-w-[160px] truncate text-xs text-zinc-400">
              {lastMsg || "No messages yet"}
            </p>
            {conversation.unreadCount > 0 && (
              <span
                className={cn(
                  "flex h-6 min-w-6 shrink-0 items-center justify-center rounded-full px-2",
                  "bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white",
                  "text-[10px] font-bold shadow-[0_0_20px_rgba(168,85,247,0.45)]"
                )}
              >
              {conversation.unreadCount > 99 ? "99+" : conversation.unreadCount}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}
