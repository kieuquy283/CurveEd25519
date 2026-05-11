/**
 * Message composer component for sending messages and typing indicators.
 */

"use client";

import React, { useState, useRef, useEffect, lazy, Suspense } from "react";
import { Send, Smile } from "lucide-react";
const AttachmentPicker = lazy(() => import("@/components/attachments/AttachmentPicker"));
import { websocketService } from "@/services/websocket";
import { useChatStore } from "@/store/useChatStore";
import { useTypingStore } from "@/store/useTypingStore";
import { TransportPacketType, TransportPacket } from "@/types/packets";
import { ChatMessage } from "@/types/models";

interface MessageComposerProps {
  conversationId: string;
}

export function MessageComposer({ conversationId }: MessageComposerProps) {
  const [text, setText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastTypingRef = useRef<number>(0);

  // select only what we need to avoid rerenders
  const addMessage = useChatStore((s) => s.addMessage);
  const getConversation = useChatStore((s) => s.getConversations);
  const setTyping = useTypingStore((s) => s.setTyping);

  const conversations = getConversation();
  const conversation = conversations.find((c) => c.id === conversationId);

  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
    };
  }, []);

  const handleInputChange = (value: string) => {
    setText(value);

    // Send typing indicators
    const now = Date.now();
    if (now - lastTypingRef.current > 1000) {
      lastTypingRef.current = now;
      setTyping(conversation?.peerId || "", value.length > 0);

      if (value.length > 0) {
        websocketService.sendTypingStart(
          "frontend",
          conversation?.peerId || ""
        ).catch((e) => console.error("Failed to send typing start:", e));
      }
    }

    // Schedule typing stop
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    typingTimeoutRef.current = setTimeout(async () => {
      if (value.length > 0) {
        setTyping(conversation?.peerId || "", false);
        try {
          await websocketService.sendTypingStop(
            "frontend",
            conversation?.peerId || ""
          );
        } catch (e) {
          console.error("Failed to send typing stop:", e);
        }
      }
    }, 3000);
  };

  const handleSend = async () => {
    if (!text.trim() || !conversation) {
      return;
    }

    setIsSending(true);

    try {
      // Create optimistic message
      const messageId = `msg-${Date.now()}-${Math.random()}`;
      const now = new Date();
      const optimisticMessage: ChatMessage = {
        id: messageId,
        conversationId,
        from: "frontend",
        to: conversation.peerId,
        text: text.trim(),
        timestamp: now.toISOString(),
        status: "pending",
      };

      // Add to store immediately (optimistic)
      addMessage(optimisticMessage);

      // Send packet
      const packet: TransportPacket = {
        packet_id: messageId,
        packet_type: TransportPacketType.MESSAGE,
        sender_id: "frontend",
        receiver_id: conversation.peerId,
        created_at: now.toISOString(),
        requires_ack: true,
        payload: {
          envelope: {
            text: text.trim(),
          },
        },
      };

      await websocketService.sendPacket(packet);

      // Clear input
      setText("");
      setTyping(conversation.peerId, false);

      // Stop typing indicator
      try {
        await websocketService.sendTypingStop(
          "frontend",
          conversation.peerId
        );
      } catch (e) {
        console.error("Failed to send typing stop:", e);
      }
    } catch (error) {
      console.error("Failed to send message:", error);
      // TODO: Show error notification
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="px-6 py-4 border-t border-zinc-800 bg-zinc-950">
      <div className="flex items-end gap-3">
        <Suspense fallback={<div className="w-9 h-9" /> }>
          <AttachmentPicker conversationId={conversationId} />
        </Suspense>

        {/* Input */}
        <div className="flex-1 relative">
          <input
            type="text"
            value={text}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors resize-none"
          />
        </div>

        {/* Emoji button */}
        <button className="p-2 hover:bg-zinc-800 rounded-lg transition-colors">
          <Smile size={20} className="text-zinc-400" />
        </button>

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={!text.trim() || isSending}
          className="p-2 hover:bg-blue-600 bg-blue-600 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Send size={20} className="text-white" />
        </button>
      </div>
    </div>
  );
}
