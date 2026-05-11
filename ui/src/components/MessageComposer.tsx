"use client";

import React, {
  useCallback,
  useRef,
  useState,
} from "react";

import { Send } from "lucide-react";

import { useChatStore } from "@/store/useChatStore";
import { websocketService } from "@/services/websocket";

import {
  buildPacketId,
  buildTimestamp,
  PacketType,
} from "@/types/packets";

const CURRENT_USER_ID = "frontend";
const API_BASE_URL = "http://127.0.0.1:8000";

interface Props {
  conversationId: string;
}

export function MessageComposer({
  conversationId,
}: Props) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  const inputRef = useRef<HTMLInputElement | null>(null);

  const chatStore = useChatStore.getState();

  const encryptMessage = useCallback(
    async (plaintext: string) => {
      const response = await fetch(
        `${API_BASE_URL}/api/conversation/encrypt`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            sender: CURRENT_USER_ID,
            recipient: conversationId,
            plaintext,
          }),
        }
      );

      if (!response.ok) {
        const errorText = await response.text();

        console.error(
          "Encrypt API failed:",
          response.status,
          errorText
        );

        throw new Error(
          `Failed to encrypt message: ${response.status}`
        );
      }

      return response.json();
    },
    [conversationId]
  );

  const handleSend = useCallback(async () => {
    const trimmed = text.trim();

    if (!trimmed || sending) {
      return;
    }

    setSending(true);

    const messageId = crypto.randomUUID();

    const optimisticMessage = {
      id: messageId,

      conversationId,

      from: CURRENT_USER_ID,
      to: conversationId,

      text: trimmed,

      timestamp: new Date().toISOString(),

      status: "pending" as const,

      type: "text",

      cryptoDirection: "encrypt" as const,
    };

    chatStore.addMessage(optimisticMessage as any);

    setText("");

    try {
      const encrypted = await encryptMessage(trimmed);

      if (
        !encrypted?.ok ||
        !encrypted?.envelope
      ) {
        throw new Error(
          "Invalid encrypt response"
        );
      }

      chatStore.updateMessageCrypto(messageId, conversationId, {
        envelope: encrypted.envelope,
        cryptoDebug: encrypted.debug ?? null,
        cryptoDirection: "encrypt",
        status: "sent",
      });

      const packet = {
        packet_id: buildPacketId(),

        packet_type:
          PacketType.MESSAGE,

        sender_id: CURRENT_USER_ID,

        receiver_id: conversationId,

        created_at: buildTimestamp(),

        requires_ack: true,

        payload: {
          envelope:
            encrypted.envelope,
        },
      };

      try {
        await websocketService.sendPacket(
          packet as any
        );
      } catch (error) {
        console.warn(
          "WebSocket not connected. Message stored locally.",
          error
        );
      }
    } catch (error) {
      console.error(error);

      chatStore.updateMessageStatus(
        messageId,
        conversationId,
        "failed"
      );
    } finally {
      setSending(false);

      requestAnimationFrame(() => {
        inputRef.current?.focus();
      });
    }
  }, [
    text,
    sending,
    conversationId,
    encryptMessage,
    chatStore,
  ]);

  return (
    <div className="border-t border-zinc-800 p-4">
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          value={text}
          disabled={sending}
          onChange={(e) =>
            setText(e.target.value)
          }
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey
            ) {
              e.preventDefault();

              handleSend();
            }
          }}
          placeholder="Send encrypted message..."
          className="flex-1 rounded-xl bg-zinc-900 border border-zinc-800 px-4 py-3 text-sm text-zinc-100 outline-none focus:border-blue-500"
        />

        <button
          type="button"
          disabled={
            sending || !text.trim()
          }
          onClick={handleSend}
          className="rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-3 transition-colors"
        >
          <Send
            size={18}
            className="text-white"
          />
        </button>
      </div>
    </div>
  );
}

export default MessageComposer;