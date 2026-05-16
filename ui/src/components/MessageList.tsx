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
  className?: string;
}

export function MessageList({ messages, conversationId, highlightedMessageId, className }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollEndRef = useRef<HTMLDivElement>(null);
  void conversationId;

  const typingPeersMap = useTypingStore((s) => s.typingPeers);
  const typingPeers = Array.from(typingPeersMap.values()).map((typing) => typing.peerId);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 200;
    if (atBottom) scrollEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typingPeers]);

  return (
    <div ref={containerRef} className={className ?? "flex-1 min-h-0 overflow-y-auto px-5 py-4"}>
      <div className="space-y-4">
      {messages.length === 0 ? (
        <div className="flex min-h-full items-center justify-center">
          <div className="text-center text-zinc-500">
            <p className="text-sm">Đoạn chat chưa có tin nhắn</p>
            <p className="mt-1 text-xs">Bắt đầu cuộc trò chuyện an toàn</p>
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
                isFirstInGroup={idx === 0 || messages[idx - 1]?.from !== message.from}
                isLastInGroup={idx === messages.length - 1 || messages[idx + 1]?.from !== message.from}
              />
            </div>
          ))}
          {typingPeers.length > 0 && <TypingIndicator peers={typingPeers} />}
          <div ref={scrollEndRef} />
        </>
      )}
      </div>
    </div>
  );
}
