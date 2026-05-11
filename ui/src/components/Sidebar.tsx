/**
 * Sidebar — conversation list, search, connection status, profile.
 */

"use client";

import React, { useMemo, useState } from "react";
import {
  Plus,
  Settings,
  Shield,
  Search,
  Wifi,
  WifiOff,
  Loader2,
} from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { useWebSocketStore } from "@/store/useWebSocketStore";
import { ConversationList } from "@/components/ConversationList";
import { cn } from "@/lib/utils";

interface SidebarProps {
  onSelectConversation?: () => void;
}

export function Sidebar({ onSelectConversation }: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const conversationMap = useChatStore((s) => s.conversations);
  const conversations = useMemo(
    () =>
      Array.from(conversationMap.values()).sort(
        (a, b) =>
          new Date(b.lastMessageAt || b.createdAt).getTime() -
          new Date(a.lastMessageAt || a.createdAt).getTime()
      ),
    [conversationMap]
  );
  const connected = useWebSocketStore((s) => s.connected);
  const connecting = useWebSocketStore((s) => s.connecting);
  const error = useWebSocketStore((s) => s.error);
  const reconnectAttempts = useWebSocketStore((s) => s.reconnectAttempts);

  const filtered = conversations.filter((c) =>
    (c.peerName ?? c.peerId).toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="px-4 pt-4 pb-3 border-b border-[var(--border)]">
        <div className="flex items-center justify-between mb-3">
          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shadow-lg glow-primary">
              <Shield size={15} className="text-white" strokeWidth={2.5} />
            </div>
            <div>
              <h1 className="text-sm font-semibold leading-tight text-foreground">
                CurveApp
              </h1>
              <p className="text-[10px] text-muted-foreground leading-none">
                Secure Messenger
              </p>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-1">
            <button
              className="w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center transition-colors"
              title="New conversation"
            >
              <Plus size={16} className="text-muted-foreground" />
            </button>
            <button
              className="w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center transition-colors"
              title="Settings"
            >
              <Settings size={16} className="text-muted-foreground" />
            </button>
          </div>
        </div>

        {/* Connection pill */}
        <ConnectionPill
          connected={connected}
          connecting={connecting}
          error={error}
          attempts={reconnectAttempts}
        />
      </div>

      {/* ── Search ────────────────────────────────────────────────────── */}
      <div className="px-3 py-2 border-b border-[var(--border)]">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
          />
          <input
            type="search"
            placeholder="Search conversations…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={cn(
              "w-full h-8 pl-8 pr-3 rounded-lg text-sm",
              "bg-white/5 border border-[var(--border)]",
              "text-foreground placeholder:text-muted-foreground",
              "focus:outline-none focus:border-[var(--primary)]/60 focus:bg-white/8",
              "transition-colors"
            )}
          />
        </div>
      </div>

      {/* ── Conversation list ─────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <ConversationList
          conversations={filtered}
          onSelect={onSelectConversation}
        />
      </div>

      {/* ── Footer ────────────────────────────────────────────────────── */}
      <div className="px-3 py-3 border-t border-[var(--border)]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-pink-500 flex items-center justify-center text-xs font-bold text-white">
            Y
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-foreground truncate">
              You (frontend)
            </p>
            <p className="text-[10px] text-muted-foreground truncate">
              Local peer
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Connection Pill ────────────────────────────────────────────────────────────

interface ConnectionPillProps {
  connected: boolean;
  connecting: boolean;
  error: string | null;
  attempts: number;
}

function ConnectionPill({
  connected,
  connecting,
  error,
  attempts,
}: ConnectionPillProps) {
  if (connected) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-green-500/10 border border-green-500/20">
        <Wifi size={11} className="text-green-400" />
        <span className="text-[10px] font-medium text-green-400">Connected</span>
      </div>
    );
  }

  if (connecting) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-yellow-500/10 border border-yellow-500/20">
        <Loader2 size={11} className="text-yellow-400 animate-spin" />
        <span className="text-[10px] font-medium text-yellow-400">
          Connecting…
        </span>
      </div>
    );
  }

  if (error || attempts > 0) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-red-500/10 border border-red-500/20">
        <WifiOff size={11} className="text-red-400" />
        <span className="text-[10px] font-medium text-red-400 truncate">
          {attempts > 0 ? `Reconnecting… (${attempts})` : "Disconnected"}
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-white/5 border border-[var(--border)]">
      <WifiOff size={11} className="text-muted-foreground" />
      <span className="text-[10px] text-muted-foreground">Offline</span>
    </div>
  );
}
