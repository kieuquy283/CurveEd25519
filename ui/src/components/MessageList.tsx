/**
 * Message list component.
 */

"use client";

import React, { useEffect, useRef } from "react";
import { ChatMessage } from "@/types/models";
import { MessageBubble } from "@/components/MessageBubble";
import { TypingIndicator } from "@/components/TypingIndicator";
import { useTypingStore } from "@/store/useTypingStore";

interface MessageListProps {
  messages: ChatMessage[];
  conversationId: string;
  highlightedMessageId?: string | null;
}

export function MessageList({
  messages,
  conversationId,
  highlightedMessageId,
}: MessageListProps) {
  const scrollEndRef = useRef<HTMLDivElement>(null);
  void conversationId;

  const typingPeersMap = useTypingStore((s) => s.typingPeers);

  const typingPeers = Array.from(typingPeersMap.values())
    .map((typing) => typing.peerId);

  // Auto-scroll to bottom only when user is near bottom
  useEffect(() => {
    const el = scrollEndRef.current?.parentElement as HTMLElement | null;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 200;
    if (atBottom) {
      scrollEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, typingPeers]);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-black">
      {messages.length === 0 ? (
        <div className="h-full flex items-center justify-center">
          <div className="text-center text-zinc-500">
            <p className="text-sm">No messages yet</p>
            <p className="text-xs mt-1">Start a conversation</p>
          </div>
        </div>
      ) : (
        <>
          {messages.map((message, idx) => (
            <div
              key={message.id}
              id={`msg-${message.id}`}
              className={highlightedMessageId === message.id ? "rounded-lg ring-1 ring-blue-500/60 ring-offset-0" : ""}
            >
              <MessageBubble
                message={message}
                isFirstInGroup={
                  idx === 0 || messages[idx - 1]?.from !== message.from
                }
                isLastInGroup={
                  idx === messages.length - 1 || messages[idx + 1]?.from !== message.from
                }
              />
            </div>
          ))}
          {typingPeers.length > 0 && (
            <TypingIndicator peers={typingPeers} />
          )}
          <div ref={scrollEndRef} />
        </>
      )}
    </div>
  );
}
