/**
 * Core domain model types for the secure messenger frontend.
 */

import { DeliveryState } from "@/types/packets";

// ─────────────────────────────────────────────────────────────
// MESSAGE
// ─────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;

  packetId?: string;

  conversationId: string;

  from: string;

  to: string;

  text: string;

  /** message type: 'text' or 'file' */
  type?: "text" | "file";

  /** File payload when `type === 'file'` */
  file?: {
    filename: string;
    mimeType: string;
    size: number;
    content_b64?: string; // optional: present only for local/decrypted messages
  };

  /** Raw envelope when message was received/sent (encrypted envelope JSON) */
  envelope?: any;

  cryptoDebug?: unknown;
  cryptoDirection?: "encrypt" | "decrypt";

  timestamp: string;

  /**
   * sending
   * sent
   * delivered
   * read
   * failed
   */
  status: DeliveryState;

  isOptimistic?: boolean;

  edited?: boolean;

  deleted?: boolean;

  attachmentIds?: string[];
}

// ─────────────────────────────────────────────────────────────
// CONVERSATION
// ─────────────────────────────────────────────────────────────

export interface Conversation {
  id: string;

  peerId: string;

  peerName?: string;

  peerAvatar?: string;

  lastMessage?: ChatMessage;

  lastMessageAt?: string;

  unreadCount: number;

  isOnline?: boolean;

  isMuted?: boolean;

  isArchived?: boolean;

  isPinned?: boolean;

  createdAt: string;

  encrypted?: boolean;
}

// ─────────────────────────────────────────────────────────────
// CONTACT
// ─────────────────────────────────────────────────────────────

export type TrustLevel =
  | "untrusted"
  | "trusted"
  | "verified";

export interface Contact {
  id: string;

  name: string;

  peerId: string;

  avatarUrl?: string;

  x25519PublicKey?: string;

  ed25519PublicKey?: string;

  fingerprint?: string;

  trustLevel: TrustLevel;

  lastSeen?: string;

  isOnline: boolean;

  createdAt: string;
}

// ─────────────────────────────────────────────────────────────
// PROFILE
// ─────────────────────────────────────────────────────────────

export interface Profile {
  id: string;

  name: string;

  avatarUrl?: string;

  x25519PublicKey: string;

  ed25519PublicKey: string;

  fingerprint: string;

  createdAt: string;
}

// ─────────────────────────────────────────────────────────────
// TYPING
// ─────────────────────────────────────────────────────────────

export interface TypingState {
  peerId: string;

  conversationId?: string;

  isTyping: boolean;

  startedAt: number;

  expiresAt: number;
}

// ─────────────────────────────────────────────────────────────
// NOTIFICATIONS
// ─────────────────────────────────────────────────────────────

export type NotificationLevel =
  | "info"
  | "success"
  | "warning"
  | "error"
  | "message"
  | "system";

export interface AppNotification {
  id: string;

  title: string;

  body: string;

  level: NotificationLevel;

  peerId?: string;

  packetId?: string;

  metadata?: Record<string, unknown>;

  read: boolean;

  dismissed: boolean;

  createdAt: number;
}

// ─────────────────────────────────────────────────────────────
// WEBSOCKET
// ─────────────────────────────────────────────────────────────

export interface WebSocketState {
  connected: boolean;

  connecting: boolean;

  error: string | null;

  reconnectAttempts: number;

  lastConnectedAt?: string;
}

// ─────────────────────────────────────────────────────────────
// MESSAGE GROUP
// ─────────────────────────────────────────────────────────────

export interface MessageGroup {
  from: string;

  messages: ChatMessage[];

  timestamp: string;
}

// ─────────────────────────────────────────────────────────────
// ATTACHMENTS
// ─────────────────────────────────────────────────────────────

export interface Attachment {
  id: string;

  fileName: string;

  mimeType: string;

  size: number;

  url?: string;

  localUrl?: string;

  uploaded: boolean;

  uploadProgress?: number;
  metadata?: Record<string, any>;
}

// ─────────────────────────────────────────────────────────────
// UI PREFERENCES
// ─────────────────────────────────────────────────────────────

export interface UiPreferences {
  theme:
    | "dark"
    | "light"
    | "system";

  fontSize:
    | "sm"
    | "md"
    | "lg";

  compactMode: boolean;

  enableSound: boolean;

  enableDesktopNotifications: boolean;

  enableTypingIndicators: boolean;

  enableReadReceipts: boolean;

  wsEndpoint: string;

  localPeerId: string;
}