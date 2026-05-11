/**
 * Message bubble component.
 */

"use client";

import React, { useState } from "react";
import { ChatMessage } from "@/types/models";
import { CheckCheck, Check, AlertCircle, Clock } from "lucide-react";
import AttachmentBubble from "@/components/attachments/AttachmentBubble";
import CryptoTracePanel from "@/components/crypto/CryptoTracePanel";

interface MessageBubbleProps {
  message: ChatMessage;
  isFirstInGroup: boolean;
  isLastInGroup: boolean;
}

const CURRENT_USER_ID = "frontend";
const API_BASE_URL = "http://127.0.0.1:8000";

function getMessageEnvelope(message: ChatMessage): any {
  return (
    (message as any).envelope ??
    (message as any).cryptoEnvelope ??
    (message as any).metadata?.envelope ??
    null
  );
}

function getMessageDebug(message: ChatMessage): any {
  return (
    (message as any).cryptoDebug ??
    (message as any).debug ??
    (message as any).metadata?.debug ??
    null
  );
}

function MessageBubbleInner({
  message,
  isFirstInGroup,
  isLastInGroup,
}: MessageBubbleProps) {
  const isOutgoing = message.from === CURRENT_USER_ID;
  const timestamp = new Date(message.timestamp);
  const timeString = timestamp.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const [openTrace, setOpenTrace] = useState(false);
  const [traceDebug, setTraceDebug] = useState<any>(getMessageDebug(message));
  const [traceEnvelope, setTraceEnvelope] = useState<any>(
    getMessageEnvelope(message)
  );
  const [traceMode, setTraceMode] = useState<"encrypt" | "decrypt">(
    isOutgoing ? "encrypt" : "decrypt"
  );
  const [traceLoading, setTraceLoading] = useState(false);

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

    if (!envelope) {
      console.warn("No encrypted envelope available for this message.");
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

      const response = await fetch(`${API_BASE_URL}/api/conversation/decrypt`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          receiver: CURRENT_USER_ID,
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
              className={`text-left px-4 py-2 rounded-lg rounded-t-2xl break-words ${
                isOutgoing
                  ? "bg-blue-600 text-white rounded-br-none"
                  : "bg-zinc-800 text-zinc-100 rounded-bl-none"
              }`}
            >
              <p className="text-sm leading-snug">{message.text}</p>
            </button>
          )}

          <div onClick={handleOpenTrace} className="cursor-pointer">
            <AttachmentBubble message={message} />
          </div>

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
          envelope={traceEnvelope}
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
    (prev.message as any).envelope === (next.message as any).envelope &&
    (prev.message as any).cryptoDebug === (next.message as any).cryptoDebug
  );
});