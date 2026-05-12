/**
 * Message bubble component.
 */

"use client";

import React, { useState } from "react";
import { ChatMessage } from "@/types/models";
import { CheckCheck, Check, AlertCircle, Clock } from "lucide-react";
import AttachmentBubble from "@/components/attachments/AttachmentBubble";
import CryptoTracePanel from "@/components/crypto/CryptoTracePanel";
import { getConversationApiBaseUrl } from "@/services/conversationCrypto";
import { useAuthStore } from "@/store/useAuthStore";

interface MessageBubbleProps {
  message: ChatMessage;
  isFirstInGroup: boolean;
  isLastInGroup: boolean;
}

type MessageMeta = {
  envelope?: Record<string, unknown>;
  debug?: Record<string, unknown>;
};

type ExtendedChatMessage = ChatMessage & {
  cryptoEnvelope?: Record<string, unknown>;
  debug?: Record<string, unknown>;
  metadata?: MessageMeta;
};

function getMessageEnvelope(message: ChatMessage): Record<string, unknown> | null {
  const msg = message as ExtendedChatMessage;
  return (
    msg.envelope ??
    msg.cryptoEnvelope ??
    msg.metadata?.envelope ??
    null
  );
}

function getMessageDebug(message: ChatMessage): Record<string, unknown> | null {
  const msg = message as ExtendedChatMessage;
  return (
    (msg.cryptoDebug as Record<string, unknown> | null | undefined) ??
    msg.debug ??
    msg.metadata?.debug ??
    null
  );
}

function MessageBubbleInner({
  message,
  isFirstInGroup,
  isLastInGroup,
}: MessageBubbleProps) {
  const currentUserId =
    useAuthStore((state) => state.currentUser?.id) ||
    process.env.NEXT_PUBLIC_USER_ID ||
    "frontend";
  const isOutgoing = message.from === currentUserId;
  const timestamp = new Date(message.timestamp);
  const timeString = timestamp.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const [openTrace, setOpenTrace] = useState(false);
  const [traceDebug, setTraceDebug] = useState<Record<string, unknown> | null>(getMessageDebug(message));
  const [traceEnvelope, setTraceEnvelope] = useState<Record<string, unknown> | null>(
    getMessageEnvelope(message)
  );
  const [traceMode, setTraceMode] = useState<"encrypt" | "decrypt">(
    isOutgoing ? "encrypt" : "decrypt"
  );
  const [traceLoading, setTraceLoading] = useState(false);
  const availableEnvelope = getMessageEnvelope(message);
  const availableDebug = getMessageDebug(message);
  const canOpenTrace = Boolean(availableEnvelope || availableDebug);
  const traceHint =
    !canOpenTrace && message.status === "pending"
      ? "Đang mã hóa..."
      : !canOpenTrace && message.status === "failed"
        ? "Mã hóa/gửi thất bại"
        : undefined;

  let statusIcon: React.ReactElement | null = null;

  switch (message.status) {
    case "pending":
      statusIcon = <Clock size={12} className="text-zinc-500" />;
      break;
    case "sent":
      statusIcon = <Check size={12} className="text-zinc-500" />;
      break;
    case "delivered":
      statusIcon = <CheckCheck size={12} className="text-zinc-500" />;
      break;
    case "read":
      statusIcon = <CheckCheck size={12} className="text-blue-500" />;
      break;
    case "failed":
      statusIcon = <AlertCircle size={12} className="text-red-500" />;
      break;
    default:
      statusIcon = null;
  }

  const handleOpenTrace = async () => {
    const envelope = getMessageEnvelope(message);
    const existingDebug = getMessageDebug(message);

    if (!envelope && !existingDebug) {
      return;
    }

    if (isOutgoing) {
      setTraceMode("encrypt");
      setTraceEnvelope(envelope);
      setTraceDebug(existingDebug);
      setOpenTrace(true);
      return;
    }

    setTraceMode("decrypt");
    setTraceEnvelope(envelope);
    setTraceDebug(existingDebug);
    setOpenTrace(true);

    if (existingDebug) return;

    try {
      setTraceLoading(true);

      const response = await fetch(`${getConversationApiBaseUrl()}/api/conversation/decrypt`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          receiver: currentUserId,
          sender: message.from,
          envelope,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.warn("Decrypt API returned error:", response.status, errorText);
        return;
      }

      const data = await response.json();

      setTraceDebug({
        ...(data.debug ?? {}),
        verified: data.debug?.verified ?? data.verified ?? data.message?.verified,
        plaintext_size:
          data.debug?.plaintext_size ??
          data.plaintext?.length ??
          data.message?.size,
        message_type: data.message?.type ?? "text",
        filename: data.message?.filename,
        mime_type: data.message?.mime_type,
      });
    } catch (error) {
      console.error("Failed to fetch decrypt trace:", error);
    } finally {
      setTraceLoading(false);
    }
  };

  return (
    <>
      <div
        className={`flex ${isOutgoing ? "justify-end" : "justify-start"} ${
          isFirstInGroup ? "mt-2" : "mt-0.5"
        }`}
      >
        <div className="flex flex-col gap-1 max-w-xs">
          {message.text && (
            <button
              type="button"
              onClick={handleOpenTrace}
              disabled={!canOpenTrace}
              title={traceHint}
              className={`text-left px-4 py-2 rounded-lg rounded-t-2xl break-words ${
                isOutgoing
                  ? "bg-blue-600 text-white rounded-br-none"
                  : "bg-zinc-800 text-zinc-100 rounded-bl-none"
              } ${!canOpenTrace ? "cursor-default" : ""}`}
            >
              <p className="text-sm leading-snug">{message.text}</p>
            </button>
          )}

          <div
            onClick={canOpenTrace ? handleOpenTrace : undefined}
            className={canOpenTrace ? "cursor-pointer" : ""}
            title={traceHint}
          >
            <AttachmentBubble message={message} />
          </div>

          {traceHint && (
            <div className="px-2 text-xs text-zinc-400">
              {traceHint}
            </div>
          )}

          {isLastInGroup && (
            <div
              className={`flex items-center gap-1 px-2 text-xs text-zinc-500 ${
                isOutgoing ? "justify-end" : "justify-start"
              }`}
            >
              {isOutgoing && statusIcon}
              <span>{timeString}</span>
            </div>
          )}
        </div>
      </div>

      {openTrace && (
        <CryptoTracePanel
          mode={traceMode}
          envelope={traceEnvelope ?? undefined}
          debug={{
            ...(traceDebug ?? {}),
            loading: traceLoading,
          }}
          onClose={() => setOpenTrace(false)}
        />
      )}
    </>
  );
}

export const MessageBubble = React.memo(MessageBubbleInner, (prev, next) => {
  return (
    prev.message.id === next.message.id &&
    prev.message.text === next.message.text &&
    prev.message.status === next.message.status &&
    prev.isFirstInGroup === next.isFirstInGroup &&
    prev.isLastInGroup === next.isLastInGroup &&
    (prev.message as ExtendedChatMessage).envelope === (next.message as ExtendedChatMessage).envelope &&
    (prev.message as ExtendedChatMessage).cryptoDebug === (next.message as ExtendedChatMessage).cryptoDebug
  );
});
