import { useEffect } from "react";
import {
  TransportPacketType,
  TransportPacket,
  MessageEnvelope,
} from "@/types/transport";
import { useWsStore } from "@/store/useWsStore";

type Handler = (p: TransportPacket) => void;

export class WebSocketService {
  private socket: WebSocket | null = null;
  private url: string;
  private reconDelay = 500;
  private maxDelay = 30_000;
  private connectedHandler: (() => void) | null = null;
  private messageHandler: Handler | null = null;

  constructor(url = "ws://localhost:8765") {
    this.url = url;
  }

  onConnected(cb: () => void) {
    this.connectedHandler = cb;
  }

  onMessage(cb: Handler) {
    this.messageHandler = cb;
  }

  connect() {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) return;

    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      this.reconDelay = 500;
      useWsStore.getState().setConnected(true);
      this.connectedHandler?.();
      console.info("ws: connected");
    };

    this.socket.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as TransportPacket;
        this.messageHandler?.(data);
      } catch (err) {
        console.warn("ws: invalid message", err);
      }
    };

    this.socket.onclose = () => {
      useWsStore.getState().setConnected(false);
      console.info("ws: closed, reconnecting...");
      this.scheduleReconnect();
    };

    this.socket.onerror = (err) => {
      useWsStore.getState().setError(String(err));
      console.error("ws: error", err);
      try {
        this.socket?.close();
      } catch (_) {}
    };
  }

  private scheduleReconnect() {
    setTimeout(() => this.connect(), this.reconDelay);
    this.reconDelay = Math.min(this.reconDelay * 2, this.maxDelay);
  }

  sendPacket(packet: TransportPacket) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket not connected");
    }
    this.socket.send(JSON.stringify(packet));
  }

  sendTyping(from: string, to: string, isTyping = true) {
    const packet: TransportPacket = {
      packet_id: crypto.randomUUID(),
      packet_type: TransportPacketType.TYPING,
      sender_id: from,
      receiver_id: to,
      payload: { typing: isTyping },
    };
    try {
      this.sendPacket(packet);
    } catch (e) {
      console.warn(e);
    }
  }
}

export const websocketService = new WebSocketService();

// optional react hook to auto-connect in the app
export function useAutoConnect() {
  useEffect(() => {
    websocketService.connect();
  }, []);
}