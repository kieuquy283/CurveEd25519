/**
 * ChatLayout — full-screen desktop+mobile chat shell.
 * Sidebar | ChatArea with responsive collapse.
 */

"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatArea } from "@/components/ChatArea";
import { useChatStore } from "@/store/useChatStore";
import { cn } from "@/lib/utils";
import { websocketService } from "@/services/websocket";

export function ChatLayout() {
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  // On mobile: track whether sidebar or chat is shown
  const [mobileSidebar, setMobileSidebar] = useState(true);

  const showSidebar = !activeConversationId || mobileSidebar;

  return (
    <div className="flex h-full w-full overflow-hidden bg-[var(--chat-bg)]">
      {/* Sidebar panel */}
      <aside
        className={cn(
          "flex-shrink-0 flex flex-col",
          "w-full md:w-[320px] lg:w-[360px]",
          "border-r border-[var(--border)]",
          "bg-[var(--sidebar-bg)]",
          // mobile: show/hide
          "md:flex",
          activeConversationId && !mobileSidebar ? "hidden" : "flex"
        )}
      >
        <Sidebar onSelectConversation={() => setMobileSidebar(false)} />
      </aside>

      {/* Chat panel */}
      <main
        className={cn(
          "flex-1 flex flex-col min-w-0 overflow-hidden",
          "md:flex",
          activeConversationId && !mobileSidebar ? "flex" : "hidden md:flex"
        )}
      >
        {activeConversationId ? (
          <ChatArea
            conversationId={activeConversationId}
            onBack={() => setMobileSidebar(true)}
          />
        ) : (
          <EmptyState />
        )}
      </main>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center p-8 select-none">
      <div className="w-20 h-20 rounded-2xl bg-[var(--accent)] flex items-center justify-center mb-6 glow-primary">
        <svg
          width="36"
          height="36"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-[var(--accent-foreground)]"
        >
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </div>
      <h2 className="text-xl font-semibold text-foreground mb-2">
        CurveApp
      </h2>
      <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
        Select a conversation from the sidebar or start a new secure chat.
        All messages are end-to-end encrypted.
      </p>
      <div className="mt-8 flex items-center gap-2 text-xs text-muted-foreground/60">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--online-dot)] animate-pulse-dot" />
        Double Ratchet · X25519 · Ed25519
      </div>
    </div>
  );
}
