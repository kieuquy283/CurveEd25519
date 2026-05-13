"use client";

import React, { useEffect, useMemo, useState } from "react";

interface DynamicWatermarkProps {
  userEmail?: string;
  userId?: string;
  conversationId?: string;
  peerName?: string;
  enabled: boolean;
}

function shortConversationId(value?: string) {
  if (!value) return "-";
  return value.length <= 12 ? value : `${value.slice(0, 6)}...${value.slice(-4)}`;
}

export default function DynamicWatermark({
  userEmail,
  userId,
  conversationId,
  peerName,
  enabled,
}: DynamicWatermarkProps) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => setNow(new Date()), 30000);
    return () => window.clearInterval(id);
  }, [enabled]);

  const watermarkText = useMemo(() => {
    const user = userEmail || userId || "unknown";
    const time = now.toLocaleString();
    const conv = shortConversationId(conversationId);
    return `CurveEd25519 • ${user} • ${time} • ${conv}${peerName ? ` • ${peerName}` : ""}`;
  }, [conversationId, now, peerName, userEmail, userId]);

  if (!enabled) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-10 overflow-hidden select-none" aria-hidden>
      <div className="absolute inset-0 rotate-[-18deg]">
        <div className="grid h-full w-full grid-cols-4 gap-16 p-10">
          {Array.from({ length: 16 }).map((_, idx) => (
            <span key={idx} className="text-[11px] font-semibold uppercase tracking-[0.25em] text-white/10">
              {watermarkText}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
