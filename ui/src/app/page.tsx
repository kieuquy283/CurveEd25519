/**
 * Root page — renders the full ChatLayout.
 * Demo conversations are seeded for UI testing until real peers connect.
 */

"use client";

import { ChatLayout } from "@/components/ChatLayout";
// import { useDemoConversations } from "@/hooks/useDemoConversations";

export default function Home() {
  // useDemoConversations();
  return <ChatLayout />;
}
