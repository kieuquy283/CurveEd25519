/**
 * WebSocket service — singleton transport layer.
 *
 * Integrates with backend TransportServer at ws://localhost:8765.
 * Handles: connection lifecycle, AUTH handshake, reconnect with
 * exponential backoff, heartbeat PING/PONG, typed packet dispatch.
 *
 * Backend expects CONNECT packet as first message on connection
 * (maps to TransportServer._handle_connection AUTH check).
 */

import {
  TransportPacket,
  PacketType,
  buildPingPacket,
  buildConnectPacket,
  buildTypingPacket,
  buildAckPacket,
  buildPacketId,
  buildTimestamp,
} from "@/types/packets";
import { useWebSocketStore } from "@/store/useWebSocketStore";

// ─── Types ───────────────────────────────────────────────────────────────────

type PacketHandler =
  (packet: TransportPacket) => Promise<void> | void;
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

const DEFAULT_CONFIG: WebSocketServiceConfig = {
  url: "ws://localhost:8765",
  localPeerId: "frontend",
  heartbeatIntervalMs: 15_000,
  reconnectBaseDelayMs: 500,
  reconnectMaxDelayMs: 30_000,
  reconnectMaxAttempts: 20,
  connectTimeoutMs: 10_000,
};

// ─── WebSocket Service ───────────────────────────────────────────────────────

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

  // Per-type packet handlers
  private readonly packetHandlers = new Map<string, Set<PacketHandler>>();

  // Lifecycle handlers
  private readonly connectionHandlers: ConnectionHandler[] = [];
  private readonly disconnectionHandlers: ConnectionHandler[] = [];

  constructor(config: Partial<WebSocketServiceConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.reconnectDelay = this.config.reconnectBaseDelayMs;
  }

  // ─── Public API ────────────────────────────────────────────────────────────

  get peerId(): string {
    return this.config.localPeerId;
  }

  updateConfig(partial: Partial<WebSocketServiceConfig>): void {
    this.config = { ...this.config, ...partial };
  }

  async connect(): Promise<void> {
    if (this.isConnected && this.socket?.readyState === WebSocket.OPEN) return;

    const store = useWebSocketStore.getState();
    store.setConnecting(true);
    store.setError(null);

    return new Promise<void>((resolve, reject) => {
      try {
        this.socket = new WebSocket(this.config.url);

        // Connection timeout guard
        this.connectTimeoutTimer = setTimeout(() => {
          if (this.socket?.readyState !== WebSocket.OPEN) {
            this.socket?.close();
            store.setConnecting(false);
            store.setError("Connection timeout");
            reject(new Error("WebSocket connection timeout"));
          }
        }, this.config.connectTimeoutMs);

        this.socket.onopen = async () => {
          this._clearTimer("connect");

          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.reconnectDelay = this.config.reconnectBaseDelayMs;

          store.setConnected(true);
          store.setConnecting(false);
          store.setError(null);
          store.setLastConnectedAt(new Date().toISOString());

          console.info("[WS] Connected to", this.config.url);

          // Send CONNECT packet (AUTH handshake expected by TransportServer)
          await this._sendConnectHandshake();

          // Start heartbeat
          this._startHeartbeat();

          // Notify listeners
          for (const h of this.connectionHandlers) {
            try { await h(); } catch (e) { console.error("[WS] connection handler:", e); }
          }

          resolve();
        };

        this.socket.onmessage = (event: MessageEvent) => {
          this._handleRawMessage(event.data as string);
        };

        this.socket.onclose = () => {
          this._clearTimer("connect");
          this.isConnected = false;
          store.setConnected(false);
          this._stopHeartbeat();

          console.info("[WS] Disconnected");

          for (const h of this.disconnectionHandlers) {
            try { h(); } catch { /* ignore */ }
          }

          if (this.shouldReconnect) {
            this._scheduleReconnect();
          }
        };

        this.socket.onerror = (event: Event) => {
          this._clearTimer("connect");
          const msg = "WebSocket error";
          console.error("[WS] Error:", event);
          store.setError(msg);
          store.setConnecting(false);
          reject(new Error(msg));
        };
      } catch (err) {
        store.setConnecting(false);
        store.setError(err instanceof Error ? err.message : "Connection failed");
        reject(err);
      }
    });
  }

  async disconnect(): Promise<void> {
    this.shouldReconnect = false;
    this._stopHeartbeat();
    this._clearTimer("reconnect");
    this._clearTimer("connect");

    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    this.isConnected = false;
    useWebSocketStore.getState().setConnected(false);
    console.info("[WS] Disconnected (intentional)");
  }

  /** Send any TransportPacket to the backend. */
  async sendPacket<T extends object>(
    packet: TransportPacket<T>
  ): Promise<void> {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket not connected");
    }
    const json = JSON.stringify(packet);
    this.socket.send(json);
    console.debug("[WS] →", packet.packet_type, packet.packet_id.slice(0, 8));
  }

  /** Subscribe to packets of a specific type. Returns unsubscribe fn. */
  onPacket<T extends object = Record<string, unknown>>(
    packetType: PacketType | string,
    handler: PacketHandler
  ): () => void {
    const key = String(packetType);
    if (!this.packetHandlers.has(key)) {
      this.packetHandlers.set(key, new Set());
    }
    this.packetHandlers.get(key)!.add(handler);
    return () => this.packetHandlers.get(key)?.delete(handler);
  }

  /** Subscribe to connection established event. */
  onConnected(handler: ConnectionHandler): () => void {
    this.connectionHandlers.push(handler);
    return () => {
      const i = this.connectionHandlers.indexOf(handler);
      if (i !== -1) this.connectionHandlers.splice(i, 1);
    };
  }

  /** Subscribe to disconnection event. */
  onDisconnected(handler: ConnectionHandler): () => void {
    this.disconnectionHandlers.push(handler);
    return () => {
      const i = this.disconnectionHandlers.indexOf(handler);
      if (i !== -1) this.disconnectionHandlers.splice(i, 1);
    };
  }

  /** Send a TYPING_START or TYPING_STOP packet. */
  async sendTypingStart(senderId: string, receiverId: string): Promise<void> {
    const packet = buildTypingPacket(senderId, receiverId, true);
    await this.sendPacket(packet);
  }

  async sendTypingStop(senderId: string, receiverId: string): Promise<void> {
    const packet = buildTypingPacket(senderId, receiverId, false);
    await this.sendPacket(packet);
  }

  /** Check if socket is currently open. */
  connected(): boolean {
    return this.isConnected && this.socket?.readyState === WebSocket.OPEN;
  }

  // ─── Private ───────────────────────────────────────────────────────────────

  private async _sendConnectHandshake(): Promise<void> {
    try {
      const packet = buildConnectPacket(this.config.localPeerId);
      await this.sendPacket(packet);
      console.debug("[WS] AUTH/CONNECT handshake sent");
    } catch (err) {
      console.warn("[WS] Failed to send CONNECT handshake:", err);
    }
  }

  private _handleRawMessage(raw: string): void {
    let packet: TransportPacket<Record<string, unknown>>;
    try {
      packet = JSON.parse(raw) as TransportPacket;
    } catch (err) {
      console.warn("[WS] Invalid JSON from server:", err);
      return;
    }

    const type = String(packet.packet_type);
    console.debug("[WS] ←", type, packet.packet_id?.slice(0, 8) ?? "?");

    // Internal: handle PONG silently
    if (type === PacketType.PONG) return;

    // Dispatch to registered handlers
    const handlers = this.packetHandlers.get(type);
    if (handlers && handlers.size > 0) {
      for (const handler of handlers) {
        Promise.resolve(handler(packet)).catch((e) =>
          console.error(`[WS] handler error for ${type}:`, e)
        );
      }
    }
  }

  private _startHeartbeat(): void {
    this._stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (!this.connected()) return;
      const ping = buildPingPacket(this.config.localPeerId);
      this.sendPacket(ping).catch((e) =>
        console.warn("[WS] Heartbeat PING failed:", e)
      );
    }, this.config.heartbeatIntervalMs);
  }

  private _stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.config.reconnectMaxAttempts) {
      useWebSocketStore.getState().setError("Max reconnect attempts reached");
      return;
    }

    this.reconnectAttempts++;
    const store = useWebSocketStore.getState();
    store.setReconnectAttempts(this.reconnectAttempts);

    console.info(`[WS] Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      if (this.shouldReconnect) {
        this.connect().catch((e) =>
          console.error("[WS] Reconnect failed:", e)
        );
      }
    }, this.reconnectDelay);

    // Exponential backoff
    this.reconnectDelay = Math.min(
      this.reconnectDelay * 2,
      this.config.reconnectMaxDelayMs
    );
  }

  private _clearTimer(type: "reconnect" | "connect"): void {
    if (type === "reconnect" && this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (type === "connect" && this.connectTimeoutTimer !== null) {
      clearTimeout(this.connectTimeoutTimer);
      this.connectTimeoutTimer = null;
    }
  }
}

// ─── Singleton ───────────────────────────────────────────────────────────────

export const websocketService = new WebSocketService();
