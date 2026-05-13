/**
 * ChatLayout — full-screen desktop+mobile chat shell.
 * Sidebar | ChatArea with responsive collapse.
 */

"use client";

import React, { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatArea } from "@/components/ChatArea";
import { useChatStore } from "@/store/useChatStore";
import { cn } from "@/lib/utils";
import { useTheme } from "@/hooks/useTheme";

export function ChatLayout() {
  useTheme();
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const [mobileSidebar, setMobileSidebar] = useState(true);

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#050816] text-zinc-100">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-24 h-96 w-96 rounded-full bg-violet-600/25 blur-3xl" />
        <div className="absolute bottom-0 right-1/4 h-[32rem] w-[32rem] rounded-full bg-blue-600/20 blur-3xl" />
        <div className="absolute top-1/3 right-0 h-80 w-80 rounded-full bg-fuchsia-600/10 blur-3xl" />
      </div>
      <div className="relative z-10 grid h-screen w-full gap-3 p-3 md:p-4 lg:grid-cols-[360px_minmax(0,1fr)]">
      <aside
        className={cn(
          "flex min-h-0 flex-col",
          "w-full",
          "rounded-[2rem] border border-white/10 bg-slate-950/70 shadow-[0_0_60px_rgba(79,70,229,0.2)] backdrop-blur-xl",
          "md:flex",
          activeConversationId && !mobileSidebar ? "hidden" : "flex"
        )}
      >
        <Sidebar onSelectConversation={() => setMobileSidebar(false)} />
      </aside>

      <main
        className={cn(
          "flex min-w-0 flex-1 flex-col overflow-hidden",
          "md:flex",
          activeConversationId && !mobileSidebar ? "flex" : "hidden md:flex"
        )}
      >
        {activeConversationId ? (
          <ChatArea conversationId={activeConversationId} onBack={() => setMobileSidebar(true)} />
        ) : (
          <EmptyState />
        )}
      </main>
      </div>
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
      <h2 className="text-xl font-semibold text-foreground mb-2">CurveApp</h2>
      <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
        Chọn cuộc trò chuyện từ thanh bên hoặc bắt đầu cuộc trò chuyện an toàn mới.
        Tất cả tin nhắn đều được mã hóa đầu-cuối.
      </p>
      <div className="mt-8 flex items-center gap-2 text-xs text-muted-foreground/60">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--online-dot)] animate-pulse-dot" />
        Double Ratchet · X25519 · Ed25519
      </div>
    </div>
  );
}
