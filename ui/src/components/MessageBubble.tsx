"use client";

import React, { useEffect, useState } from "react";
import { ChatMessage } from "@/types/models";
import { CheckCheck, Check, AlertCircle, Clock, Copy, Eye } from "lucide-react";
import AttachmentBubble from "@/components/attachments/AttachmentBubble";
import CryptoTracePanel from "@/components/crypto/CryptoTracePanel";
import { getConversationApiBaseUrl } from "@/services/conversationCrypto";
import { useAuthStore } from "@/store/useAuthStore";
import { useSettingsStore } from "@/store/useSettingsStore";
import { copyEncryptedMessage } from "@/lib/clipboardCrypto";
import { usePrivacyReveal } from "@/hooks/usePrivacyReveal";
import { logAuditEvent } from "@/services/audit";

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
  return msg.envelope ?? msg.cryptoEnvelope ?? msg.metadata?.envelope ?? null;
}

function getMessageDebug(message: ChatMessage): Record<string, unknown> | null {
  const msg = message as ExtendedChatMessage;
  return (msg.cryptoDebug as Record<string, unknown> | null | undefined) ?? msg.debug ?? msg.metadata?.debug ?? null;
}

function MessageBubbleInner({ message, isFirstInGroup, isLastInGroup }: MessageBubbleProps) {
  const currentUserId = useAuthStore((state) => state.currentUser?.id) || process.env.NEXT_PUBLIC_USER_ID || "frontend";
  const currentUserEmail = useAuthStore((state) => state.currentUser?.email);
  const prefs = useSettingsStore((s) => s.prefs);

  const isOutgoing = message.from === currentUserId;
  const timestamp = new Date(message.timestamp);
  const timeString = timestamp.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

  const [openTrace, setOpenTrace] = useState(false);
  const [traceDebug, setTraceDebug] = useState<Record<string, unknown> | null>(getMessageDebug(message));
  const [traceEnvelope, setTraceEnvelope] = useState<Record<string, unknown> | null>(getMessageEnvelope(message));
  const [traceMode, setTraceMode] = useState<"encrypt" | "decrypt">(isOutgoing ? "encrypt" : "decrypt");
  const [traceLoading, setTraceLoading] = useState(false);

  const { revealed, reveal } = usePrivacyReveal(message.id, prefs.autoHideMs);
  const messageExt = message as ChatMessage & {
    expires_at?: string;
    view_once?: boolean;
    viewed_at?: string;
    metadata?: {
      expires_at?: string;
      view_once?: boolean;
      viewed_at?: string;
    };
  };

  const expiresAtRaw = messageExt.expires_at || messageExt.metadata?.expires_at;
  const viewOnce = Boolean(messageExt.view_once ?? messageExt.metadata?.view_once);
  const viewedAt = messageExt.viewed_at || messageExt.metadata?.viewed_at;
  const isExpired = Boolean(expiresAtRaw && Date.now() > new Date(expiresAtRaw).getTime());
  const isViewOnceConsumed = Boolean(viewOnce && viewedAt);

  const privacyEnabled = prefs.privacyMode && prefs.blurMessages;
  const isSensitiveHidden = privacyEnabled && !revealed;

  useEffect(() => {
    if (!prefs.auditLeakEvents) return;
    logAuditEvent({
      event_type: prefs.privacyMode ? "privacy_mode_enabled" : "privacy_mode_disabled",
      user_email: currentUserEmail || currentUserId,
      conversation_id: message.conversationId,
      message_id: message.id,
    });
    // only first mount for this bubble when setting changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefs.privacyMode]);

  const availableEnvelope = getMessageEnvelope(message);
  const availableDebug = getMessageDebug(message);
  const canOpenTrace = Boolean(availableEnvelope || availableDebug);
  const traceHint = !canOpenTrace && message.status === "pending"
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
      statusIcon = <CheckCheck size={12} className="text-blue-200" />;
      break;
    case "failed":
      statusIcon = <AlertCircle size={12} className="text-red-400" />;
      break;
    default:
      statusIcon = null;
  }

  const handleOpenTrace = async () => {
    const envelope = getMessageEnvelope(message);
    const existingDebug = getMessageDebug(message);
    if (!envelope && !existingDebug) return;

    setTraceMode(isOutgoing ? "encrypt" : "decrypt");
    setTraceEnvelope(envelope);
    setTraceDebug({
      ...(existingDebug ?? {}),
      sender: (existingDebug as Record<string, unknown> | null)?.signature_key_owner ?? (existingDebug as Record<string, unknown> | null)?.sender ?? message.from,
      receiver: (existingDebug as Record<string, unknown> | null)?.encryption_key_owner ?? (existingDebug as Record<string, unknown> | null)?.receiver ?? message.to,
    });
    setOpenTrace(true);

    if (isOutgoing || existingDebug) return;

    try {
      setTraceLoading(true);
      const response = await fetch(`${getConversationApiBaseUrl()}/api/conversation/decrypt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ receiver: currentUserId, sender: message.from, envelope }),
      });
      if (!response.ok) return;
      const data = await response.json();
      setTraceDebug({
        ...(data.debug ?? {}),
        sender: data.debug?.signature_key_owner ?? data.debug?.sender ?? message.from,
        receiver: data.debug?.encryption_key_owner ?? data.debug?.receiver ?? currentUserId,
        verified: data.debug?.verified ?? data.verified ?? data.message?.verified,
        plaintext_size: data.debug?.plaintext_size ?? data.plaintext?.length ?? data.message?.size,
        message_type: data.message?.type ?? "text",
        filename: data.message?.filename,
        mime_type: data.message?.mime_type,
      });
    } catch {
      // ignore
    } finally {
      setTraceLoading(false);
    }
  };

  const revealTemporarily = () => {
    reveal();
    if (prefs.auditLeakEvents) {
      void logAuditEvent({
        event_type: "message_revealed",
        user_email: currentUserEmail || currentUserId,
        conversation_id: message.conversationId,
        message_id: message.id,
        peer_email: isOutgoing ? message.to : message.from,
      });
    }
  };

  const handleCopyEncrypted = async () => {
    try {
      await copyEncryptedMessage(message);
      alert("Đã sao chép bản mã hóa");
      if (prefs.auditLeakEvents) {
        void logAuditEvent({
          event_type: "message_copied_encrypted",
          user_email: currentUserEmail || currentUserId,
          conversation_id: message.conversationId,
          message_id: message.id,
          peer_email: isOutgoing ? message.to : message.from,
        });
      }
    } catch {
      alert("Không thể sao chép vào clipboard");
    }
  };

  return (
    <>
      <div className={`flex ${isOutgoing ? "justify-end" : "justify-start"} ${isFirstInGroup ? "mt-2" : "mt-0.5"}`}>
        <div className="flex max-w-[72%] flex-col gap-1">
          {message.text && (
            <div className="relative">
              {isExpired ? (
                <div
                  className={`rounded-3xl px-4 py-3 text-sm leading-relaxed ${
                    isOutgoing
                      ? "rounded-br-lg bg-gradient-to-br from-zinc-700 to-zinc-600 text-zinc-200"
                      : "rounded-bl-lg border border-white/10 bg-white/[0.07] text-zinc-200"
                  }`}
                >
                  Tin nhắn đã hết hạn
                </div>
              ) : isViewOnceConsumed ? (
                <div
                  className={`rounded-3xl px-4 py-3 text-sm leading-relaxed ${
                    isOutgoing
                      ? "rounded-br-lg bg-gradient-to-br from-zinc-700 to-zinc-600 text-zinc-200"
                      : "rounded-bl-lg border border-white/10 bg-white/[0.07] text-zinc-200"
                  }`}
                >
                  Tin nhắn xem một lần đã bị ẩn
                </div>
              ) : (
                <button
                type="button"
                onClick={prefs.revealOnClick && isSensitiveHidden ? revealTemporarily : handleOpenTrace}
                onMouseEnter={prefs.revealOnHover && isSensitiveHidden ? revealTemporarily : undefined}
                onCopy={(event) => {
                  event.preventDefault();
                  void handleCopyEncrypted();
                }}
                onContextMenu={prefs.privacyMode && prefs.disableContextMenu ? (event) => event.preventDefault() : undefined}
                disabled={!canOpenTrace && !isSensitiveHidden}
                title={traceHint}
                className={`rounded-3xl px-4 py-3 text-left text-sm leading-relaxed shadow-lg ${
                  isOutgoing
                    ? "rounded-br-lg bg-gradient-to-br from-violet-600 to-blue-600 text-white shadow-[0_0_30px_rgba(59,130,246,0.22)]"
                    : "rounded-bl-lg border border-white/10 bg-white/[0.07] text-zinc-100"
                } ${!canOpenTrace && !isSensitiveHidden ? "cursor-default" : ""}`}
              >
                <span className={`block transition duration-200 ${isSensitiveHidden ? "blur-sm select-none" : "blur-0 select-text"}`}>{message.text}</span>
              </button>
              )}

              {isSensitiveHidden && !isExpired && !isViewOnceConsumed && (
                <div className="pointer-events-none absolute inset-x-0 bottom-2 flex justify-center">
                  <span className="rounded-full bg-black/40 px-2 py-1 text-xs text-zinc-300">Nhấn để xem · Tự ẩn sau {Math.round(prefs.autoHideMs / 1000)} giây</span>
                </div>
              )}
            </div>
          )}

          <div
            className={isSensitiveHidden ? "rounded-2xl transition duration-200 blur-sm" : "rounded-2xl transition duration-200 blur-0"}
            onMouseEnter={prefs.revealOnHover && isSensitiveHidden ? revealTemporarily : undefined}
            onClick={prefs.revealOnClick && isSensitiveHidden ? revealTemporarily : undefined}
            onContextMenu={prefs.privacyMode && prefs.disableContextMenu ? (event) => event.preventDefault() : undefined}
          >
            <AttachmentBubble message={message} />
          </div>

          <div className={`flex items-center gap-2 ${isOutgoing ? "justify-end" : "justify-start"} px-1`}>
            <button
              type="button"
              onClick={handleCopyEncrypted}
              className="inline-flex items-center gap-1 rounded-xl border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-zinc-200 hover:bg-white/[0.08]"
            >
              <Copy size={12} />
              Copy encrypted
            </button>

            {prefs.privacyMode && (
              <button
                type="button"
                onClick={revealTemporarily}
                className="inline-flex items-center gap-1 rounded-xl border border-violet-400/20 bg-violet-500/10 px-2.5 py-1 text-xs text-violet-200 hover:bg-violet-500/20"
              >
                <Eye size={12} />
                Show temporarily
              </button>
            )}

            {canOpenTrace && (
              <button
                type="button"
                onClick={handleOpenTrace}
                className="rounded-xl border border-violet-400/20 bg-violet-500/10 px-3 py-1.5 text-xs text-violet-200 hover:bg-violet-500/20"
              >
                Crypto trace / Envelope
              </button>
            )}
          </div>

          {traceHint && <div className="px-2 text-xs text-zinc-400">{traceHint}</div>}

          {isLastInGroup && (
            <div className={`mt-1 flex items-center gap-1 px-2 text-[11px] ${isOutgoing ? "justify-end text-blue-100/80" : "justify-start text-zinc-500"}`}>
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
          debug={{ ...(traceDebug ?? {}), loading: traceLoading }}
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
