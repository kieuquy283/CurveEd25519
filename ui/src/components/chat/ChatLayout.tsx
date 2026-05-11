"use client";
import React, { useEffect, useState } from "react";
import ChatSidebar from "./ChatSidebar";
import ChatTopbar from "./ChatTopbar";
import ChatContainer from "./ChatContainer";

interface Props {
  children?: React.ReactNode;
}

const ChatLayout: React.FC<Props> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(() => {
    try {
      return typeof window !== "undefined" && window.matchMedia("(min-width: 768px)").matches;
    } catch {
      return true;
    }
  });

  // update on viewport changes
  useEffect(() => {
    try {
      const mq = window.matchMedia("(min-width: 768px)");
      const cb = (e: MediaQueryListEvent) => setSidebarOpen(e.matches);
      mq.addEventListener("change", cb);
      return () => mq.removeEventListener("change", cb);
    } catch {
      // ignore
    }
  }, []);

  return (
    <div className="h-screen flex bg-slate-900 text-slate-100">
      <ChatSidebar open={sidebarOpen} onToggle={() => setSidebarOpen((v) => !v)} />

      <div className="flex-1 flex flex-col relative">
        <ChatTopbar onToggleSidebar={() => setSidebarOpen((v) => !v)} />
        <ChatContainer>{children}</ChatContainer>

        {/* mobile overlay when sidebar is open */}
        {!sidebarOpen ? null : (
          <div
            className={`md:hidden fixed inset-0 bg-black/40 z-30 transition-opacity ${
              sidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none"
            }`}
            onClick={() => setSidebarOpen(false)}
            aria-hidden
          />
        )}
      </div>
    </div>
  );
};

export default ChatLayout;
