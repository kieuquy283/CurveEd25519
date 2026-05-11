/**
 * Message bubble component.
 */

"use client";

import React from "react";
import { ChatMessage } from "@/types/models";
import { CheckCheck, Check, AlertCircle, Clock } from "lucide-react";
import AttachmentBubble from "@/components/attachments/AttachmentBubble";

interface MessageBubbleProps {
  message: ChatMessage;
  isFirstInGroup: boolean;
  isLastInGroup: boolean;
}

function MessageBubbleInner({
  message,
  isFirstInGroup,
  isLastInGroup,
}: MessageBubbleProps) {
  const isOutgoing = message.from === "frontend"; // Simplified: frontend is local user
  const timestamp = new Date(message.timestamp);
  const timeString = timestamp.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });

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

  return (
    <div
      className={`flex ${isOutgoing ? "justify-end" : "justify-start"} ${
        isFirstInGroup ? "mt-2" : "mt-0.5"
      }`}
    >
      <div className="flex flex-col gap-1 max-w-xs">
        <div
          className={`px-4 py-2 rounded-lg rounded-t-2xl break-words ${
            isOutgoing
              ? "bg-blue-600 text-white rounded-br-none"
              : "bg-zinc-800 text-zinc-100 rounded-bl-none"
          }`}
        >
          <p className="text-sm leading-snug">{message.text}</p>
        </div>
        <AttachmentBubble message={message} />
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
  );
}

export const MessageBubble = React.memo(MessageBubbleInner, (prev, next) => {
  // Shallow compare essential props to avoid unnecessary rerenders
  return (
    prev.message.id === next.message.id &&
    prev.message.text === next.message.text &&
    prev.message.status === next.message.status &&
    prev.isFirstInGroup === next.isFirstInGroup &&
    prev.isLastInGroup === next.isLastInGroup
  );
});
