export enum TransportPacketType {
  MESSAGE = "message",
  ACK = "ack",
  PING = "ping",
  PONG = "pong",
  SESSION_INIT = "session_init",
  SESSION_REKEY = "session_rekey",
  SESSION_CLOSE = "session_close",
  PRESENCE = "presence",
  TYPING = "typing",
  ATTACHMENT = "attachment",
  ERROR = "error",
}

export interface TransportPacket {
  packet_id: string;
  packet_type: TransportPacketType | string;
  protocol_version?: number;
  sender_id: string;
  receiver_id: string;
  created_at?: string;
  requires_ack?: boolean;
  encrypted?: boolean;
  compressed?: boolean;
  priority?: number;
  metadata?: Record<string, unknown>;
  payload: Record<string, unknown>;
}

export interface MessageEnvelope {
  text?: string;
  [key: string]: unknown;
}

export interface ChatMessage {
  id: string;
  from: string;
  to: string;
  text: string;
  ts?: string;
}
