"use client";
import { AttachmentMeta } from "@/types/attachments";
import { useAttachmentStore } from "@/store/useAttachmentStore";
import { buildPacketId, buildTimestamp, PacketType, TransportPacket } from "@/types/packets";
import { websocketService } from "@/services/websocket";
import { getCurrentUserId } from "@/store/useAuthStore";

const objectUrlMap = new Map<string, string>();

export function createPreviewUrl(id: string, file: File): string {
  const url = URL.createObjectURL(file);
  objectUrlMap.set(id, url);
  return url;
}

export function revokePreviewUrl(id: string): void {
  const url = objectUrlMap.get(id);
  if (url) {
    URL.revokeObjectURL(url);
    objectUrlMap.delete(id);
  }
}

export async function sendAttachmentMeta(a: AttachmentMeta, receiverId: string): Promise<void> {
  const packet: TransportPacket = {
    packet_id: a.id,
    packet_type: PacketType.ATTACHMENT_META,
    sender_id: getCurrentUserId(),
    receiver_id: receiverId,
    created_at: buildTimestamp(),
    requires_ack: true,
    payload: {
      attachment_id: a.id,
      file_name: a.fileName,
      mime_type: a.mimeType,
      size: a.size,
    },
  } as TransportPacket;

  // Send over websocket; backend expected to handle binary upload separately
  await websocketService.sendPacket(packet);
}

export function simulateUploadProgress(id: string, onProgress?: (p:number)=>void): Promise<void> {
  return new Promise((resolve) => {
    let p = 0;
    const iv = setInterval(() => {
      p = Math.min(100, p + Math.floor(Math.random() * 20) + 5);
      useAttachmentStore.getState().setProgress(id, p);
      if (onProgress) onProgress(p);
      if (p >= 100) {
        clearInterval(iv);
        // mark uploaded (no real URL)
        useAttachmentStore.getState().markUploaded(id, undefined);
        resolve();
      }
    }, 300 + Math.random() * 700);
  });
}
