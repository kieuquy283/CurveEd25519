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
        "w-full flex items-center gap-3 px-3 py-2.5 mx-1 rounded-xl",
        "text-left transition-all duration-150 group",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
        isActive
          ? "bg-white/8 text-foreground"
          : "hover:bg-white/5 text-foreground"
      )}
    >
      {/* Avatar */}
      <div className="relative flex-shrink-0">
        <div
          className={cn(
            "w-10 h-10 rounded-full bg-gradient-to-br flex items-center justify-center",
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
              "absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full",
              "bg-[var(--online-dot)] border-2 border-[var(--sidebar-bg)]"
            )}
          />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-1 mb-0.5">
          <span className="text-sm font-medium truncate">{name}</span>
          {lastTime && (
            <span className="text-[10px] text-muted-foreground flex-shrink-0">
              {lastTime}
            </span>
          )}
        </div>
        <div className="flex items-center justify-between gap-1">
          <p className="text-xs text-muted-foreground truncate max-w-[160px]">
            {lastMsg || "No messages yet"}
          </p>
          {conversation.unreadCount > 0 && (
            <span
              className={cn(
                "flex-shrink-0 min-w-[18px] h-[18px] px-1 rounded-full",
                "bg-primary text-primary-foreground",
                "text-[10px] font-bold flex items-center justify-center"
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
