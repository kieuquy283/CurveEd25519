"use client";
import React, { useEffect, useState } from "react";
import { websocketService, useAutoConnect } from "@/services/websocket";
import { useWsStore } from "@/store/useWsStore";
import { TransportPacketType, TransportPacket } from "@/types/transport";

export default function ChatWindow() {
  useAutoConnect();

  const connected = useWsStore((s) => s.connected);
  const messages = useWsStore((s) => s.messages);
  const addMessage = useWsStore((s) => s.addMessage);
  const setTypingPeers = useWsStore((s) => s.setTypingPeers);

  const [text, setText] = useState("");

  useEffect(() => {
    websocketService.onMessage((packet: TransportPacket) => {
      if (packet.packet_type === TransportPacketType.MESSAGE) {
        const envelope = packet.payload["envelope"] as any;
        addMessage({ id: packet.packet_id, from: packet.sender_id, to: packet.receiver_id, text: envelope?.text || "", ts: packet.created_at });
      }
      if (packet.packet_type === TransportPacketType.TYPING) {
        const payload = packet.payload as any;
        const typing = payload?.typing;
        if (typing) {
          setTypingPeers([packet.sender_id]);
          setTimeout(() => setTypingPeers([]), 3000);
        }
      }
    });
  }, [addMessage, setTypingPeers]);

  const send = () => {
    if (!text.trim()) return;
    const packet: TransportPacket = {
      packet_id: crypto.randomUUID(),
      packet_type: TransportPacketType.MESSAGE,
      sender_id: "frontend",
      receiver_id: "server",
      payload: { envelope: { text } },
    };
    try {
      websocketService.sendPacket(packet);
      addMessage({ id: packet.packet_id, from: packet.sender_id, to: packet.receiver_id, text, ts: new Date().toISOString() });
      setText("");
    } catch (e) {
      console.warn(e);
    }
  };

  const onTyping = (v: string) => {
    setText(v);
    websocketService.sendTyping("frontend", "server", v.length > 0);
  };

  return (
    <div className="p-4 max-w-2xl mx-auto">
      <div className="mb-4">WebSocket: {connected ? "connected" : "disconnected"}</div>

      <div className="border rounded-md p-3 mb-3 h-96 overflow-auto bg-white">
        {messages.map((m) => (
          <div key={m.id} className="mb-2">
            <strong className="mr-2">{m.from}:</strong>
            <span>{m.text}</span>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <input value={text} onChange={(e) => onTyping(e.target.value)} className="flex-1 border rounded px-2 py-1" />
        <button onClick={send} className="px-3 py-1 bg-sky-600 text-white rounded">Send</button>
      </div>
    </div>
  );
}
