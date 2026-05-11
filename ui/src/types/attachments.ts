/**
 * Attachment-related types for the frontend.
 */
import { TransportPacket } from "@/types/packets";

export interface AttachmentMeta {
  id: string;
  fileName: string;
  mimeType: string;
  size: number;
  url?: string; // optional URL when uploaded
  localUrl?: string; // object URL for preview
  uploaded: boolean;
}

export interface AttachmentUploadPacketPayload {
  attachment_id: string;
  file_name: string;
  mime_type: string;
  size: number;
}

export type AttachmentMetaPacket = TransportPacket<AttachmentUploadPacketPayload>;
