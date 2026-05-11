// Re-export from canonical location for backward compatibility
export type { TransportPacket, TransportMetadata } from "@/types/packets";
export { PacketType as TransportPacketType } from "@/types/packets";
export type { ChatMessage, WebSocketState } from "@/types/models";

export interface MessageEnvelope {
  text?: string;
  [key: string]: unknown;
}
