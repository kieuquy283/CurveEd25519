"use client";

import React, { useRef } from "react";
import { Paperclip } from "lucide-react";
import { useAttachmentStore } from "@/store/useAttachmentStore";
import {
  createPreviewUrl,
  simulateUploadProgress,
} from "@/services/attachments";
import { websocketService } from "@/services/websocket";
import {
  buildPacketId,
  buildTimestamp,
  PacketType,
} from "@/types/packets";
import { useChatStore } from "@/store/useChatStore";
import { getCurrentUserId } from "@/store/useAuthStore";
import { getApiBaseUrl } from "@/config/env";
import { ChatMessage } from "@/types/models";
const API_BASE_URL = getApiBaseUrl();

function arrayBufferToBase64(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";

  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }

  return btoa(binary);
}

export default function AttachmentPicker({
  conversationId,
}: {
  conversationId: string;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const addLocalAttachment = useAttachmentStore((s) => s.addLocalAttachment);

  const onFile = async (file: File) => {
    if (file.type !== "application/pdf") {
      console.warn("Only application/pdf is currently supported");
      return;
    }

    const chatStore = useChatStore.getState();
    const currentUserId = getCurrentUserId();

    const attachmentId = `att-${Date.now()}-${Math.random()
      .toString(36)
      .slice(2, 8)}`;

    const messageId = `msg-${Date.now()}-${Math.random()}`;
    const now = new Date().toISOString();

    const localUrl = createPreviewUrl(attachmentId, file);

    addLocalAttachment({
      id: attachmentId,
      fileName: file.name,
      mimeType: file.type || "application/pdf",
      size: file.size,
      localUrl,
      uploaded: false,
    });

    const pendingMessage: ChatMessage = {
      id: messageId,
      conversationId,
      from: currentUserId,
      to: conversationId,
      text: "",
      timestamp: now,
      status: "pending",
      type: "file",
      file: {
        filename: file.name,
        mimeType: file.type || "application/pdf",
        size: file.size,
      },
      attachmentIds: [attachmentId],
      cryptoDirection: "encrypt",
    };
    chatStore.addMessage(pendingMessage);

    try {
      const contentB64 = arrayBufferToBase64(await file.arrayBuffer());

      const response = await fetch(`${API_BASE_URL}/api/conversation/encrypt-file`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          sender: currentUserId,
          recipient: conversationId,
          filename: file.name,
          mime_type: file.type || "application/pdf",
          content_b64: contentB64,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Encrypt-file failed: ${response.status} ${errorText}`);
      }

      const data = await response.json();

      if (!data.ok || !data.envelope) {
        throw new Error("Invalid encrypt-file response");
      }

      useAttachmentStore.getState().markUploaded(attachmentId, undefined, {
        envelope: data.envelope,
        debug: data.debug,
      });

      chatStore.updateMessageCrypto(messageId, conversationId, {
        envelope: data.envelope,
        cryptoDebug: data.debug,
        cryptoDirection: "encrypt",
        status: "sent",
      });

      const packet = {
        packet_id: buildPacketId(),
        packet_type: PacketType.MESSAGE,
        sender_id: currentUserId,
        receiver_id: conversationId,
        created_at: buildTimestamp(),
        requires_ack: true,
        payload: {
          envelope: data.envelope,
        },
      };

      try {
        await websocketService.sendPacket(packet);
      } catch (error) {
        console.warn(
          "WebSocket not connected, encrypted file kept locally.",
          error
        );
      }

      simulateUploadProgress(attachmentId).catch(() => {});
    } catch (error) {
      console.error(error);

      chatStore.updateMessageStatus(messageId, conversationId, "failed");
    }
  };

  const onSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];

    if (file) {
      onFile(file);
    }

    event.currentTarget.value = "";
  };

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={onSelect}
      />

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
        title="Attach encrypted PDF"
      >
        <Paperclip size={20} className="text-zinc-400" />
      </button>
    </div>
  );
}

