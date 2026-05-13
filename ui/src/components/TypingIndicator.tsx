/**
 * Typing indicator component.
 */

"use client";

import React from "react";

interface TypingIndicatorProps {
  peers: string[];
}

export function TypingIndicator({ peers }: TypingIndicatorProps) {
  if (peers.length === 0) return null;

  return (
    <div className="flex items-center gap-2">
      <div className="rounded-3xl rounded-bl-lg border border-white/10 bg-white/[0.06] px-4 py-2">
        <div className="flex gap-1 items-center">
          <div className="w-2 h-2 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
          <div className="w-2 h-2 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
          <div className="w-2 h-2 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
      <span className="text-xs text-zinc-500">
        {peers.length === 1 ? `${peers[0]} is typing` : "Multiple users typing"}
      </span>
    </div>
  );
}
