"use client";

import React from "react";
import { ArrowLeft, Circle, Info } from "lucide-react";
import { Conversation } from "@/types/models";

interface ChatHeaderProps {
  conversation: Conversation;
  onBack?: () => void;
  infoPanelOpen?: boolean;
  onToggleInfoPanel?: () => void;
  connectionStatusLabel?: string;
  onOpenConnectionSecurity?: () => void;
}

export function ChatHeader({
  conversation,
  onBack,
  infoPanelOpen = false,
  onToggleInfoPanel,
  connectionStatusLabel,
  onOpenConnectionSecurity,
}: ChatHeaderProps) {
  const displayName = conversation.peerName || conversation.peerId;
  const avatarLetter = displayName.charAt(0).toUpperCase();

  return (
    <header className="flex items-center justify-between border-b border-white/10 bg-slate-950/70 px-4 py-4 backdrop-blur-xl md:px-6">
      <div className="flex min-w-0 items-center gap-3">
        {onBack && (
          <button
            onClick={onBack}
            className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-zinc-300 transition-colors hover:bg-violet-500/15 hover:text-white md:hidden"
            aria-label="Back"
          >
            <ArrowLeft size={20} />
          </button>
        )}

        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-blue-500 text-sm font-semibold text-white">
          {avatarLetter}
        </div>

        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold text-white md:text-base">{displayName}</h2>
          <button
            type="button"
            onClick={onOpenConnectionSecurity}
            className="mt-0.5 flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200"
          >
            <Circle size={7} className="fill-emerald-500 text-emerald-500" />
            <span>{connectionStatusLabel || "Không kiểm tra được kết nối"}</span>
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onToggleInfoPanel}
          className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-violet-300 transition hover:bg-violet-500/15 hover:text-white"
          aria-label="Conversation info"
          aria-pressed={infoPanelOpen}
        >
          <Info size={20} />
        </button>
      </div>
    </header>
  );
}
