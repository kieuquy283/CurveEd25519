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
      <div className="flex flex-col items-center justify-center h-full py-16 px-6 text-center">
        <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center mb-3">
          <MessageSquare size={20} className="text-muted-foreground" />
        </div>
        <p className="text-sm text-muted-foreground">No conversations yet</p>
        <p className="text-xs text-muted-foreground/60 mt-1">
          Start a new chat to begin
        </p>
      </div>
    );
  }

  return (
    <div className="py-1">
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
