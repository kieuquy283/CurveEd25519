"use client";

import React from "react";

import { useChatStore } from "@/store/useChatStore";

import { MessageList } from "@/components/MessageList";
import { MessageComposer } from "@/components/MessageComposer";
import { ChatHeader } from "@/components/ChatHeader";

interface ChatAreaProps {
  conversationId: string;
  onBack?: () => void;
}

export function ChatArea({
  conversationId,
  onBack,
}: ChatAreaProps) {
  const conversations = useChatStore(
    (s) => s.conversations
  );

  const activeConversation =
    conversations.get(conversationId);

  const messages = useChatStore((s) =>
    s.getMessages(conversationId)
  );

  if (!activeConversation) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-zinc-500">
        Conversation not found
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-black">
      {/* Header */}
      <ChatHeader
        conversation={activeConversation}
        onBack={onBack}
      />

      {/* Messages */}
      <MessageList
        messages={messages}
        conversationId={conversationId}
      />

      {/* Composer */}
      <MessageComposer
        conversationId={conversationId}
      />
    </div>
  );
}