/**
 * WebSocket service â€” singleton transport layer.
 */

import {
  TransportPacket,
  PacketType,
  buildPingPacket,
  buildConnectPacket,
  buildTypingPacket,
  buildAckPacket,
} from "@/types/packets";

import { useWebSocketStore } from "@/store/useWebSocketStore";
import { decryptIncomingMessage } from "@/services/conversationCrypto";
import { getWsUrl } from "@/config/env";

type PacketHandler = (packet: TransportPacket) => Promise<void> | void;
type ConnectionHandler = () => Promise<void> | void;

interface WebSocketServiceConfig {
  url: string;
  localPeerId: string;
  heartbeatIntervalMs: number;
  reconnectBaseDelayMs: number;
  reconnectMaxDelayMs: number;
  reconnectMaxAttempts: number;
  connectTimeoutMs: number;
}

function resolveDefaultWsUrl(): string {
  return getWsUrl().trim();
}

const DEFAULT_CONFIG: WebSocketServiceConfig = {
  url: resolveDefaultWsUrl(),
  localPeerId:
    process.env.NEXT_PUBLIC_USER_ID ||
    "frontend",
  heartbeatIntervalMs: 15_000,
  reconnectBaseDelayMs: 500,
  reconnectMaxDelayMs: 30_000,
  reconnectMaxAttempts: 20,
  connectTimeoutMs: 10_000,
};

class WebSocketService {
  private socket: WebSocket | null = null;
  private config: WebSocketServiceConfig;
  private reconnectAttempts = 0;
  private reconnectDelay: number;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private connectTimeoutTimer: ReturnType<typeof setTimeout> | null = null;
  private isConnected = false;
  private shouldReconnect = true;
  private hasLoggedCurrentOutage = false;

  private readonly packetHandlers = new Map<string, Set<PacketHandler>>();
  private readonly connectionHandlers: ConnectionHandler[] = [];
  private readonly disconnectionHandlers: ConnectionHandler[] = [];

  constructor(config: Partial<WebSocketServiceConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.reconnectDelay = this.config.reconnectBaseDelayMs;
  }

  get peerId(): string {
    return this.config.localPeerId;
  }

  updateConfig(partial: Partial<WebSocketServiceConfig>): void {
    this.config = { ...this.config, ...partial };
  }

  async connect(): Promise<void> {
    if (this.isConnected && this.socket?.readyState === WebSocket.OPEN) return;

    this.shouldReconnect = true;

    const store = useWebSocketStore.getState();
    store.setConnecting(true);
    store.setError(null);

    return new Promise<void>((resolve, reject) => {
      try {
        console.info(`[WS] Connecting to ${this.config.url}`);
        this.socket = new WebSocket(this.config.url);

        this.connectTimeoutTimer = setTimeout(() => {
          if (this.socket?.readyState !== WebSocket.OPEN) {
            this.socket?.close();
            store.setConnecting(false);
            store.setError("Connection timeout");
            reject(new Error("WebSocket connection timeout"));
          }
        }, this.config.connectTimeoutMs);

        this.socket.onopen = async () => {
          this.clearConnectTimer();

          this.isConnected = true;
          this.hasLoggedCurrentOutage = false;
          this.reconnectAttempts = 0;
          this.reconnectDelay = this.config.reconnectBaseDelayMs;

          store.setConnected(true);
          store.setConnecting(false);
          store.setError(null);
          store.setLastConnectedAt(new Date().toISOString());

          await this.sendConnectHandshake();
          this.startHeartbeat();

          for (const handler of this.connectionHandlers) {
            try {
              await handler();
            } catch (error) {
              console.error("[WS] connection handler error:", error);
            }
          }

          resolve();
        };

        this.socket.onmessage = async (event: MessageEvent) => {
          await this.handleRawMessage(event.data as string);
        };

        this.socket.onclose = (event: CloseEvent) => {
          this.clearConnectTimer();
          this.isConnected = false;
          console.warn(
            `[WS] closed url=${this.config.url} code=${event.code} reason=${event.reason || "<empty>"}`
          );

          store.setConnected(false);
          store.setConnecting(false);

          this.stopHeartbeat();

          for (const handler of this.disconnectionHandlers) {
            try {
              handler();
            } catch {
              // ignore
            }
          }

          if (this.shouldReconnect) {
            this.scheduleReconnect();
          }
        };

        this.socket.onerror = (event: Event) => {
          this.clearConnectTimer();
          const errorMessage = `WebSocket connection failed: ${this.config.url}. Ensure WS server is running.`;
          if (!this.hasLoggedCurrentOutage) {
            this.hasLoggedCurrentOutage = true;
            console.warn("[WS] error event:", event);
          }

          store.setError(errorMessage);
          store.setConnecting(false);

          reject(new Error(errorMessage));
        };
      } catch (error) {
        store.setConnecting(false);
        store.setError(
          error instanceof Error ? error.message : "Connection failed"
        );
        reject(error);
      }
    });
  }

  async disconnect(): Promise<void> {
    this.shouldReconnect = false;

    this.stopHeartbeat();
    this.clearReconnectTimer();
    this.clearConnectTimer();

    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    this.isConnected = false;
    useWebSocketStore.getState().setConnected(false);
  }

  async sendPacket<T extends object>(packet: TransportPacket<T>): Promise<void> {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket not connected");
    }

    this.socket.send(JSON.stringify(packet));
  }

  onPacket(
    packetType: PacketType | string,
    handler: PacketHandler
  ): () => void {
    const key = String(packetType);

    if (!this.packetHandlers.has(key)) {
      this.packetHandlers.set(key, new Set());
    }

    this.packetHandlers.get(key)!.add(handler);

    return () => {
      this.packetHandlers.get(key)?.delete(handler);
    };
  }

  onConnected(handler: ConnectionHandler): () => void {
    this.connectionHandlers.push(handler);

    return () => {
      const index = this.connectionHandlers.indexOf(handler);
      if (index !== -1) this.connectionHandlers.splice(index, 1);
    };
  }

  onDisconnected(handler: ConnectionHandler): () => void {
    this.disconnectionHandlers.push(handler);

    return () => {
      const index = this.disconnectionHandlers.indexOf(handler);
      if (index !== -1) this.disconnectionHandlers.splice(index, 1);
    };
  }

  async sendTypingStart(senderId: string, receiverId: string): Promise<void> {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
    const packet = buildTypingPacket(senderId, receiverId, true);
    await this.sendPacket(packet);
  }

  async sendTypingStop(senderId: string, receiverId: string): Promise<void> {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
    const packet = buildTypingPacket(senderId, receiverId, false);
    await this.sendPacket(packet);
  }

  private async sendConnectHandshake(): Promise<void> {
    const packet = buildConnectPacket(this.config.localPeerId);
    await this.sendPacket(packet);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();

    this.heartbeatTimer = setInterval(async () => {
      try {
        const packet = buildPingPacket(this.config.localPeerId);
        await this.sendPacket(packet);
      } catch (error) {
        console.error("[WS] heartbeat failed:", error);
      }
    }, this.config.heartbeatIntervalMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private async handleRawMessage(raw: string): Promise<void> {
    try {
      const packet = JSON.parse(raw) as TransportPacket;

      if (packet.packet_type === PacketType.MESSAGE) {
        await this.handleIncomingEncryptedMessage(packet);
      }

      if (packet.requires_ack) {
        await this.sendAck(packet);
      }

      const handlers = this.packetHandlers.get(String(packet.packet_type));

      if (handlers) {
        for (const handler of handlers) {
          try {
            await handler(packet);
          } catch (error) {
            console.error("[WS] packet handler error:", error);
          }
        }
      }
    } catch (error) {
      console.error("[WS] failed to handle message:", error);
    }
  }

  private async handleIncomingEncryptedMessage(
    packet: TransportPacket<Record<string, unknown>>
  ): Promise<void> {
    try {
      if (!packet.payload?.envelope) {
        return;
      }

      const decrypted = await decryptIncomingMessage({
        receiver: this.config.localPeerId,
        sender: packet.sender_id || "unknown",
        envelope: packet.payload.envelope,
      });

      packet.payload = {
        ...packet.payload,
        plaintext: decrypted.plaintext,
        debug: decrypted.debug,
      };
    } catch (error) {
      console.error("[WS] failed to decrypt incoming message:", error);
    }
  }

  private async sendAck(packet: TransportPacket): Promise<void> {
    try {
      const ack = buildAckPacket(
        this.config.localPeerId,
        packet.sender_id,
        packet.packet_id
      );

      await this.sendPacket(ack);
    } catch (error) {
      console.error("[WS] failed to send ACK:", error);
    }
  }

  private scheduleReconnect(): void {
    const store = useWebSocketStore.getState();

    if (this.reconnectAttempts >= this.config.reconnectMaxAttempts) {
      store.setError("Reconnect attempts exceeded");
      store.setConnecting(false);
      return;
    }

    this.reconnectAttempts += 1;
    store.setReconnectAttempts(this.reconnectAttempts);
    store.setConnecting(true);

    const delay = Math.min(
      this.reconnectDelay,
      this.config.reconnectMaxDelayMs
    );

    this.reconnectTimer = setTimeout(() => {
      this.connect().catch(() => {
        // Error state is already updated in connect/onerror; avoid log spam.
      });
    }, delay);

    this.reconnectDelay = Math.min(
      this.reconnectDelay * 2,
      this.config.reconnectMaxDelayMs
    );
  }

  private clearConnectTimer(): void {
    if (this.connectTimeoutTimer) {
      clearTimeout(this.connectTimeoutTimer);
      this.connectTimeoutTimer = null;
    }
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

export const websocketService = new WebSocketService();

