/**
 * Transport packet + websocket protocol types.
 * Must remain compatible with backend packet schema.
 */

// ─────────────────────────────────────────────────────────────
// PACKET TYPES
// ─────────────────────────────────────────────────────────────

export enum PacketType {
  // Messaging
  MESSAGE = "message",
  ACK = "ack",
  ERROR = "error",

  // Session / Crypto
  SESSION_INIT = "session_init",
  SESSION_ACCEPT = "session_accept",
  SESSION_CLOSE = "session_close",
  REKEY = "rekey",
  RATCHET_STEP = "ratchet_step",

  // Transport
  CONNECT = "connect",
  DISCONNECT = "disconnect",
  PING = "ping",
  PONG = "pong",

  // Presence / Typing
  PRESENCE = "presence",
  TYPING_START = "typing_start",
  TYPING_STOP = "typing_stop",

  // Sync
  SYNC_REQUEST = "sync_request",
  SYNC_RESPONSE = "sync_response",

  // Attachments
  ATTACHMENT_META = "attachment_meta",
  ATTACHMENT_CHUNK = "attachment_chunk",
  ATTACHMENT_COMPLETE = "attachment_complete",

  // System
  SYSTEM = "system",
  EVENT = "event",
}

export {
  PacketType as TransportPacketType,
};

// ─────────────────────────────────────────────────────────────
// DELIVERY STATE
// ─────────────────────────────────────────────────────────────

export type DeliveryState =
  | "pending"
  | "queued"
  | "sent"
  | "delivered"
  | "acked"
  | "read"
  | "failed"
  | "expired"
  | "dropped";

// ─────────────────────────────────────────────────────────────
// TRANSPORT METADATA
// ─────────────────────────────────────────────────────────────

export interface TransportMetadata {
  trace_id?: string;

  route?: string;

  ttl_seconds?: number;

  compression?: string;

  content_type?: string;

  custom?: Record<string, unknown>;

  ephemeral?: boolean;

  requires_ack?: boolean;

  persist?: boolean;
}

// ─────────────────────────────────────────────────────────────
// BASE TRANSPORT PACKET
// ─────────────────────────────────────────────────────────────

export interface TransportPacket<
  TPayload extends object = Record<string, unknown>,
> {
  packet_id: string;

  packet_type: PacketType | string;

  protocol_version?: number;

  sender_id: string;

  receiver_id: string;

  created_at?: string;

  requires_ack?: boolean;

  encrypted?: boolean;

  compressed?: boolean;

  priority?: number;

  metadata?: TransportMetadata;

  payload: TPayload;
}

// ─────────────────────────────────────────────────────────────
// PAYLOADS
// ─────────────────────────────────────────────────────────────

export interface MessageEnvelope {
  text?: string;

  message_id?: string;

  ciphertext?: string;

  signature?: string;

  [key: string]: unknown;
}

export interface MessagePayload {
  envelope: MessageEnvelope;
}

export interface AckPayload {
  packet_id: string;

  status:
    | "acked"
    | "failed"
    | "dropped";

  reason?: string;
}

export interface TypingPayload {
  typing: boolean;
}

export interface PresencePayload {
  status:
    | "online"
    | "offline"
    | "away";

  last_seen?: string;
}

export interface ErrorPayload {
  error_code: string;

  message: string;

  details?: Record<
    string,
    unknown
  >;
}

export interface SessionInitPayload {
  public_key?: string;

  session_id?: string;

  [key: string]: unknown;
}

// ─────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────

export function buildPacketId(): string {
  return `${Date.now()}-${crypto.randomUUID()}`;
}

export function buildTimestamp(): string {
  return new Date()
    .toISOString()
    .replace(".000Z", "Z");
}

// ─────────────────────────────────────────────────────────────
// BUILDERS
// ─────────────────────────────────────────────────────────────

export function buildMessagePacket(
  senderId: string,
  receiverId: string,
  envelope: MessageEnvelope,
): TransportPacket<MessagePayload> {
  return {
    packet_id: buildPacketId(),

    packet_type:
      PacketType.MESSAGE,

    sender_id: senderId,

    receiver_id: receiverId,

    created_at:
      buildTimestamp(),

    requires_ack: true,

    encrypted: true,

    compressed: false,

    priority: 0,

    payload: {
      envelope,
    },
  };
}

export function buildAckPacket(
  senderId: string,
  receiverId: string,
  originalPacketId: string,
): TransportPacket<AckPayload> {
  return {
    packet_id: buildPacketId(),

    packet_type: PacketType.ACK,

    sender_id: senderId,

    receiver_id: receiverId,

    created_at:
      buildTimestamp(),

    requires_ack: false,

    encrypted: false,

    payload: {
      packet_id:
        originalPacketId,

      status: "acked",
    },
  };
}

export function buildPingPacket(
  senderId: string,
): TransportPacket {
  return {
    packet_id: buildPacketId(),

    packet_type:
      PacketType.PING,

    sender_id: senderId,

    receiver_id: "server",

    created_at:
      buildTimestamp(),

    requires_ack: false,

    encrypted: false,

    payload: {},
  };
}

export function buildTypingPacket(
  senderId: string,
  receiverId: string,
  isTyping: boolean,
): TransportPacket<TypingPayload> {
  return {
    packet_id: buildPacketId(),

    packet_type: isTyping
      ? PacketType.TYPING_START
      : PacketType.TYPING_STOP,

    sender_id: senderId,

    receiver_id: receiverId,

    created_at:
      buildTimestamp(),

    requires_ack: false,

    encrypted: false,

    metadata: {
      ephemeral: true,

      requires_ack: false,

      persist: false,
    },

    payload: {
      typing: isTyping,
    },
  };
}

export function buildConnectPacket(
  peerId: string,
): TransportPacket {
  return {
    packet_id: buildPacketId(),

    packet_type:
      PacketType.CONNECT,

    sender_id: peerId,

    receiver_id: "server",

    created_at:
      buildTimestamp(),

    requires_ack: false,

    encrypted: false,

    payload: {
      peer_id: peerId,
    },
  };
}