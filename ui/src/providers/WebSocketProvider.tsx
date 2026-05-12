/**
 * WebSocket provider â€” manages connection lifecycle and packet routing.
 * Wires transport packets to Zustand stores.
 */

"use client";

import React, { useEffect, useRef } from "react";

import { websocketService } from "@/services/websocket";
import { useChatStore } from "@/store/useChatStore";
import { useTypingStore } from "@/store/useTypingStore";
import { useNotificationStore } from "@/store/useNotificationStore";
import { useContactStore } from "@/store/useContactStore";
import { useAuthStore } from "@/store/useAuthStore";
import { useSettingsStore } from "@/store/useSettingsStore";

import {
  AckPayload,
  MessagePayload,
  PacketType,
  TransportPacket,
} from "@/types/packets";

import { ChatMessage } from "@/types/models";
import { saveConversationMessage } from "@/services/conversations";

interface ParsedAttachment {
  id: string;
  fileName: string;
  mimeType: string;
  size: number;
  dataBase64?: string;
  url?: string;
  uploaded: boolean;
  crypto?: {
    encrypted?: boolean;
    decrypted?: boolean;
    encryption?: string;
    keyExchange?: string;
    kdf?: string;
    signature?: string;
  };
}

function parseIncomingEnvelope(rawText: string) {

  let text = rawText;
  let type: "text" | "file" = "text";
  let attachments: ParsedAttachment[] = [];
  let file: Record<string, unknown> | undefined;

  try {
    const parsed = JSON.parse(rawText) as Record<string, unknown>;

    if (
      parsed &&
      typeof parsed === "object" &&
      parsed.type === "file" &&
      parsed.attachment
    ) {
      const attachment = parsed.attachment as Record<string, unknown>;

      const id =
        typeof attachment.id === "string"
          ? attachment.id
          : crypto.randomUUID();

      const fileName =
        typeof attachment.fileName === "string"
          ? attachment.fileName
          : typeof attachment.filename === "string"
            ? attachment.filename
            : "attachment";

      const mimeType =
        typeof attachment.mimeType === "string"
          ? attachment.mimeType
          : typeof attachment.mime_type === "string"
            ? attachment.mime_type
            : "application/octet-stream";

      const size =
        typeof attachment.size === "number"
          ? attachment.size
          : 0;

      const dataBase64 =
        typeof attachment.dataBase64 === "string"
          ? attachment.dataBase64
          : typeof attachment.content_b64 === "string"
            ? attachment.content_b64
            : undefined;

      const cryptoInfo =
        attachment.crypto &&
        typeof attachment.crypto === "object"
          ? attachment.crypto
          : {
              encrypted: true,
              decrypted: true,
              encryption: "ChaCha20-Poly1305",
              keyExchange: "X25519",
              kdf: "HKDF-SHA256",
              signature: "Ed25519",
            };

      const url = dataBase64
        ? `data:${mimeType};base64,${dataBase64}`
        : undefined;

      type = "file";
      text =
        typeof parsed.text === "string" &&
        parsed.text.trim()
          ? parsed.text
          : `ðŸ“Ž ${fileName}`;

      attachments = [
        {
          id,
          fileName,
          mimeType,
          size,
          dataBase64,
          url,
          uploaded: true,
          crypto: cryptoInfo as ParsedAttachment["crypto"],
        },
      ];

      file = {
        id,
        filename: fileName,
        fileName,
        mimeType,
        mime_type: mimeType,
        size,
        content_b64: dataBase64,
        dataBase64,
        url,
        crypto: cryptoInfo,
      };
    }
  } catch {
    // text thÆ°á»ng, giá»¯ nguyÃªn rawText
  }

  return {
    text,
    type,
    attachments,
    file,
  };
}

export function WebSocketProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const cleanupRef =
    useRef<ReturnType<typeof setInterval> | null>(
      null
    );
  const initialWsErrorNotifiedRef = useRef(false);
  const currentUserId = useAuthStore(
    (state) => state.currentUser?.id
  ) || process.env.NEXT_PUBLIC_USER_ID || "frontend";
  const wsEndpoint = useSettingsStore(
    (state) => state.prefs.wsEndpoint
  );
  const effectiveWsEndpoint =
    typeof wsEndpoint === "string" &&
    wsEndpoint.trim().length > 0
      ? wsEndpoint.trim()
      : undefined;

  useEffect(() => {
    websocketService.updateConfig({
      ...(effectiveWsEndpoint
        ? { url: effectiveWsEndpoint }
        : {}),
      localPeerId: currentUserId,
    });

    const unsubMessage = websocketService.onPacket(
      PacketType.MESSAGE,
      async (packet: TransportPacket) => {
        const chatStore = useChatStore.getState();

        const payload =
          packet.payload as Partial<MessagePayload>;

        const envelope =
          payload.envelope &&
          typeof payload.envelope === "object"
            ? (payload.envelope as Record<
                string,
                unknown
              >)
            : {};
        const plaintext =
          typeof payload.plaintext === "string"
            ? payload.plaintext
            : typeof envelope.text === "string"
              ? envelope.text
              : "";

        const parsedEnvelope =
          parseIncomingEnvelope(plaintext);

        const conversationId = packet.sender_id;
        const currentUser =
          (useAuthStore.getState().currentUser?.id ||
            useAuthStore.getState().currentUser?.email ||
            packet.receiver_id) ?? packet.receiver_id;

        const message: ChatMessage = {
          id: packet.packet_id,
          conversationId,

          from: packet.sender_id,
          to: packet.receiver_id,

          text: parsedEnvelope.text,
          type: parsedEnvelope.type,

          file: parsedEnvelope.file as ChatMessage["file"],
          attachments: parsedEnvelope.attachments,

          envelope:
            Object.keys(envelope).length > 0
              ? envelope
              : undefined,

          timestamp:
            packet.created_at ??
            new Date().toISOString(),

          status: "delivered",
          packetId: packet.packet_id,

          cryptoDirection: "decrypt",
          cryptoDebug:
            (payload.debug as Record<
              string,
              unknown
            >) ?? undefined,
        };

        chatStore.addMessage(message);
        chatStore.addConversation({
          id: conversationId,
          peerId: packet.sender_id,
          peerName: packet.sender_id,
          createdAt: packet.created_at ?? new Date().toISOString(),
          lastMessageAt: packet.created_at ?? new Date().toISOString(),
          unreadCount: 0,
          encrypted: true,
        });

        try {
          await saveConversationMessage(conversationId, {
            sender_email: packet.sender_id,
            receiver_email: currentUser,
            packet_id: packet.packet_id,
            message_type: parsedEnvelope.type,
            ciphertext_envelope: envelope,
            plaintext_preview: parsedEnvelope.text.slice(0, 200),
            attachment_json:
              parsedEnvelope.attachments.length > 0
                ? (parsedEnvelope.attachments[0] as unknown as Record<string, unknown>)
                : undefined,
            crypto_debug:
              (payload.debug as Record<string, unknown> | undefined) || undefined,
            status: "delivered",
          });
        } catch (persistError) {
          console.warn("[WebSocketProvider] saveConversationMessage failed:", persistError);
        }

        const activeId =
          chatStore.activeConversationId;

        if (activeId !== conversationId) {
          chatStore.updateConversation(
            conversationId,
            {
              unreadCount:
                (chatStore.conversations.get(
                  conversationId
                )?.unreadCount ?? 0) + 1,
            }
          );
        }

        useNotificationStore
          .getState()
          .addNotification({
            title: packet.sender_id,
            body: parsedEnvelope.text.slice(0, 120),
            level: "message",
            peerId: packet.sender_id,
            packetId: packet.packet_id,
            read: false,
          });

      }
    );

    const unsubAck = websocketService.onPacket(
      PacketType.ACK,
      (packet: TransportPacket) => {
        const chatStore = useChatStore.getState();

        const ackPayload =
          packet.payload as Partial<AckPayload>;

        const originalId = ackPayload.packet_id;

        if (!originalId) {
          return;
        }

        for (const [
          convId,
          msgs,
        ] of chatStore.messages.entries()) {
          for (const msg of msgs) {
            if (
              msg.packetId === originalId ||
              msg.id === originalId
            ) {
              chatStore.updateMessageStatus(
                msg.id,
                convId,
                "acked"
              );
              return;
            }
          }
        }
      }
    );

    const unsubTypingStart =
      websocketService.onPacket(
        PacketType.TYPING_START,
        (packet: TransportPacket) => {
          useTypingStore
            .getState()
            .setRemoteTyping(
              packet.sender_id,
              true
            );
        }
      );

    const unsubTypingStop =
      websocketService.onPacket(
        PacketType.TYPING_STOP,
        (packet: TransportPacket) => {
          useTypingStore
            .getState()
            .setRemoteTyping(
              packet.sender_id,
              false
            );
        }
      );

    const unsubError = websocketService.onPacket(
      PacketType.ERROR,
      (packet: TransportPacket) => {
        const payload =
          packet.payload as Record<
            string,
            unknown
          >;

        const message =
          typeof payload.message === "string"
            ? payload.message
            : "Unknown server error";

        useNotificationStore
          .getState()
          .addNotification({
            title: "Server Error",
            body: message,
            level: "error",
            packetId: packet.packet_id,
            read: false,
          });
      }
    );

    const unsubPresence =
      websocketService.onPacket(
        PacketType.PRESENCE,
        (packet: TransportPacket) => {
          const payload =
            packet.payload as Record<
              string,
              unknown
            >;

          const status =
            payload.status as string | undefined;

          const isOnline = status === "online";

          useChatStore
            .getState()
            .updateConversation(
              packet.sender_id,
              { isOnline }
            );

          try {
            const contactStore =
              useContactStore.getState();

            contactStore.updateContact(
              packet.sender_id,
              { isOnline }
            );
          } catch {
            // ignore
          }
        }
      );

    websocketService.connect().catch(() => {
      // Connection errors are already reflected in WebSocket store/UI state.
      // Avoid duplicate console spam during reconnect cycles.
      if (!initialWsErrorNotifiedRef.current) {
        initialWsErrorNotifiedRef.current = true;
        useNotificationStore.getState().addNotification({
          title: "WebSocket Disconnected",
          body: "Cannot connect to realtime server. Check WS endpoint/server status.",
          level: "warning",
          read: false,
        });
      }
    });

    cleanupRef.current = setInterval(() => {
      const typingStore =
        useTypingStore.getState();

      const now = Date.now();

      typingStore.typingPeers.forEach(
        (typing, peerId) => {
          if (typing.expiresAt <= now) {
            typingStore.clearTypingPeer(peerId);
          }
        }
      );
    }, 1000);

    return () => {
      unsubMessage();
      unsubAck();
      unsubTypingStart();
      unsubTypingStop();
      unsubError();
      unsubPresence();

      if (cleanupRef.current) {
        clearInterval(cleanupRef.current);
        cleanupRef.current = null;
      }

      websocketService.disconnect();
    };
  }, [currentUserId, effectiveWsEndpoint]);

  return <>{children}</>;
}

