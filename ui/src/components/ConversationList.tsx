/**
 * ConversationList — renders the list of conversations in the sidebar.
 */

"use client";

import React from "react";
import { Conversation } from "@/types/models";
import { ConversationItem } from "@/components/ConversationItem";
import { useChatStore } from "@/store/useChatStore";
import { MessageSquare } from "lucide-react";

interface ConversationListProps {
  conversations: Conversation[];
  onSelect?: () => void;
}

export function ConversationList({
  conversations,
  onSelect,
}: ConversationListProps) {
  const activeId = useChatStore((s) => s.activeConversationId);
  const setActive = useChatStore((s) => s.setActiveConversation);
  const clearUnread = useChatStore((s) => s.clearUnreadCount);

  const handleSelect = (id: string) => {
    setActive(id);
    clearUnread(id);
    onSelect?.();
  };

  if (conversations.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 py-16 text-center">
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.06]">
          <MessageSquare size={20} className="text-zinc-400" />
        </div>
        <p className="text-sm text-zinc-400">Chưa có cuộc trò chuyện</p>
        <p className="mt-1 text-xs text-zinc-500">
          Start a new chat to begin
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5 p-2">
      {conversations.map((conv) => (
        <ConversationItem
          key={conv.id}
          conversation={conv}
          isActive={conv.id === activeId}
          onSelect={() => handleSelect(conv.id)}
        />
      ))}
    </div>
  );
}
