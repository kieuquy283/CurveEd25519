"use client";

import React from "react";

import {
  ArrowLeft,
  Circle,
  Info,
} from "lucide-react";

import { Conversation } from "@/types/models";

interface ChatHeaderProps {
  conversation: Conversation;
  onBack?: () => void;
}

export function ChatHeader({
  conversation,
  onBack,
}: ChatHeaderProps) {
  const displayName =
    conversation.peerName ||
    conversation.peerId;

  const avatarLetter =
    displayName.charAt(0).toUpperCase();

  return (
    <header className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4 py-3 md:px-6">
      {/* Left */}
      <div className="flex min-w-0 items-center gap-3">
        {/* Mobile back button */}
        {onBack && (
          <button
            onClick={onBack}
            className="flex h-10 w-10 items-center justify-center rounded-xl text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white md:hidden"
            aria-label="Back"
          >
            <ArrowLeft size={20} />
          </button>
        )}

        {/* Avatar */}
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 text-sm font-semibold text-white">
          {avatarLetter}
        </div>

        {/* Conversation info */}
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold text-white md:text-base">
            {displayName}
          </h2>

          <div className="mt-0.5 flex items-center gap-1 text-xs text-zinc-400">
            {conversation.isOnline ? (
              <>
                <Circle
                  size={7}
                  className="fill-emerald-500 text-emerald-500"
                />

                <span>Online</span>
              </>
            ) : (
              <span>Offline</span>
            )}
          </div>
        </div>
      </div>

      {/* Right */}
      <div className="flex items-center gap-2">
        <button
          className="flex h-10 w-10 items-center justify-center rounded-xl text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
          aria-label="Conversation info"
        >
          <Info size={20} />
        </button>
      </div>
    </header>
  );
}