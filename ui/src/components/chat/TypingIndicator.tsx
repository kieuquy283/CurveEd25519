"use client";
import React from "react";
import { useTypingStore } from "@/store/useTypingStore";
import { useChatStore } from "@/store/useChatStore";

const TypingIndicator: React.FC = () => {
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const getTypingPeers = useTypingStore((s) => s.getTypingPeers);

  if (!activeConversationId) return null;

  const peers = getTypingPeers(activeConversationId);
  if (peers.length === 0) return null;

  const label = peers.length === 1 ? `${peers[0]} is typing...` : `${peers.length} people are typing...`;

  return (
    <div className="px-4 py-2 text-sm text-slate-400">
      {label}
    </div>
  );
};

export default TypingIndicator;
