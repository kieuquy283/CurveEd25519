/**
 * WebSocket provider — manages connection lifecycle and packet routing.
 * Wires transport packets to Zustand stores.
 */

"use client";

import React, { useEffect, useRef } from "react";
import { websocketService } from "@/services/websocket";
import { useChatStore } from "@/store/useChatStore";
import { useTypingStore } from "@/store/useTypingStore";
import { useNotificationStore } from "@/store/useNotificationStore";
import { useContactStore } from "@/store/useContactStore";
import {
  PacketType,
  TransportPacket,
  AckPayload,
  MessagePayload,
} from "@/types/packets";
import { ChatMessage } from "@/types/models";

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const initializedRef = useRef(false);
  const cleanupRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    // ── MESSAGE handler ────────────────────────────────────────────────────
    const unsubMessage = websocketService.onPacket(
      PacketType.MESSAGE,
      async (packet: TransportPacket) => {
        const chatStore = useChatStore.getState();
        const payload = packet.payload as Partial<MessagePayload>;
        const envelope = payload.envelope ?? {};
        const text =
          typeof envelope.text === "string" ? envelope.text : "";

        const conversationId = packet.sender_id;

        const message: ChatMessage = {
          id: packet.packet_id,
          conversationId,
          from: packet.sender_id,
          to: packet.receiver_id,
          text,
          timestamp: packet.created_at ?? new Date().toISOString(),
          status: "delivered",
          packetId: packet.packet_id,
        };

        chatStore.addMessage(message);

        // Increment unread if conversation not active
        const activeId = chatStore.activeConversationId;
        if (activeId !== conversationId) {
          chatStore.updateConversation(conversationId, {
            unreadCount:
              (chatStore.conversations.get(conversationId)?.unreadCount ?? 0) +
              1,
          });
        }

        // Notification
        useNotificationStore.getState().addNotification({
          title: packet.sender_id,
          body: text.slice(0, 120),
          level: "message",
          peerId: packet.sender_id,
          packetId: packet.packet_id,
          read: false,
        });

        // Send ACK
        if (packet.requires_ack) {
          try {
            const { buildAckPacket } = await import("@/types/packets");
            const ack = buildAckPacket(
              packet.receiver_id,
              packet.sender_id,
              packet.packet_id
            );
            await websocketService.sendPacket(ack);
          } catch (e) {
            console.error("[WS] Failed to send ACK:", e);
          }
        }
      }
    );

    // ── ACK handler ────────────────────────────────────────────────────────
    const unsubAck = websocketService.onPacket(
      PacketType.ACK,
      (packet: TransportPacket) => {
        const chatStore = useChatStore.getState();
        const ackPayload = packet.payload as Partial<AckPayload>;
        const originalId = ackPayload.packet_id;
        if (!originalId) return;

        for (const [convId, msgs] of chatStore.messages.entries()) {
          for (const msg of msgs) {
            if (msg.packetId === originalId || msg.id === originalId) {
              chatStore.updateMessageStatus(msg.id, convId, "acked");
              return;
            }
          }
        }
      }
    );

    // ── TYPING_START handler ───────────────────────────────────────────────
    const unsubTypingStart = websocketService.onPacket(
      PacketType.TYPING_START,
      (packet: TransportPacket) => {
        useTypingStore.getState().setRemoteTyping(packet.sender_id, true);
      }
    );

    // ── TYPING_STOP handler ────────────────────────────────────────────────
    const unsubTypingStop = websocketService.onPacket(
      PacketType.TYPING_STOP,
      (packet: TransportPacket) => {
        useTypingStore.getState().setRemoteTyping(packet.sender_id, false);
      }
    );

    // ── ERROR handler ──────────────────────────────────────────────────────
    const unsubError = websocketService.onPacket(
      PacketType.ERROR,
      (packet: TransportPacket) => {
        const payload = packet.payload as Record<string, unknown>;
        const msg =
          typeof payload.message === "string"
            ? payload.message
            : "Unknown server error";

        useNotificationStore.getState().addNotification({
          title: "Server Error",
          body: msg,
          level: "error",
          packetId: packet.packet_id,
          read: false,
        });
      }
    );

    // ── PRESENCE handler ───────────────────────────────────────────────────
    const unsubPresence = websocketService.onPacket(
      PacketType.PRESENCE,
      (packet: TransportPacket) => {
        const payload = packet.payload as Record<string, unknown>;
        const status = payload.status as string | undefined;
        const isOnline = status === "online";
        useChatStore.getState().updateConversation(packet.sender_id, { isOnline });
        // Also update contact presence
        try {
          const contactStore = useContactStore.getState();
          contactStore.updateContact(packet.sender_id, { isOnline });
        } catch {
          // ignore if contact store not available
        }
      }
    );

    // ── Start connection ───────────────────────────────────────────────────
    websocketService.connect().catch((e) =>
      console.error("[WebSocketProvider] Failed to connect:", e)
    );

    // Periodic cleanup for expired typing states
    cleanupRef.current = setInterval(() => {
      const typingStore = useTypingStore.getState();
      const now = Date.now();
      // iterate and clear expired typing peers
      typingStore.typingPeers.forEach((typing, peerId) => {
        if (typing.expiresAt <= now) {
          typingStore.clearTypingPeer(peerId);
        }
      });
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
  }, []);

  return <>{children}</>;
}
