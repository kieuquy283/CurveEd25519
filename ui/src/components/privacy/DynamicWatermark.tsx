"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";

import { logWatermarkTrace } from "@/services/audit";

interface DynamicWatermarkProps {
  userEmail?: string;
  userId?: string;
  conversationId?: string;
  peerName?: string;
  peerEmail?: string;
  enabled: boolean;
}

function shortConversationId(value?: string) {
  if (!value) return "-";
  return value.length <= 12 ? value : `${value.slice(0, 6)}...${value.slice(-4)}`;
}

function normalizeEmail(value?: string) {
  const v = (value || "").trim().toLowerCase();
  return v || undefined;
}

function createTraceCode() {
  const chars = "0123456789ABCDEF";
  let out = "";
  for (let i = 0; i < 6; i += 1) {
    out += chars[Math.floor(Math.random() * chars.length)];
  }
  return `WM-${out}`;
}

function formatTimestamp(date: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function getOrCreateSessionId() {
  const key = "wm_trace_session_id";
  const existing = window.sessionStorage.getItem(key);
  if (existing) return existing;
  const created =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `wm-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
  window.sessionStorage.setItem(key, created);
  return created;
}

export default function DynamicWatermark({
  userEmail,
  userId,
  conversationId,
  peerName,
  peerEmail,
  enabled,
}: DynamicWatermarkProps) {
  const [now, setNow] = useState(() => new Date());
  const [traceCode, setTraceCode] = useState(() => createTraceCode());
  const sessionIdRef = useRef<string>("");

  useEffect(() => {
    if (!enabled) return;
    sessionIdRef.current = getOrCreateSessionId();
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    const rotateAndLog = async () => {
      const windowStart = new Date();
      const windowEnd = new Date(windowStart.getTime() + 30_000);
      const nextCode = createTraceCode();
      setNow(windowStart);
      setTraceCode(nextCode);

      const actor = normalizeEmail(userEmail) || normalizeEmail(userId);
      if (!actor) return;

      const payload = {
        trace_code: nextCode,
        user_email: actor,
        conversation_id: conversationId,
        peer_email: normalizeEmail(peerEmail),
        peer_display_name: peerName || shortConversationId(conversationId),
        session_id: sessionIdRef.current || "unknown-session",
        time_window_start: windowStart.toISOString(),
        time_window_end: windowEnd.toISOString(),
      };

      const result = await logWatermarkTrace(payload);
      if (cancelled) return;
      if (!result.ok) {
        // keep local trace code visible even if logging fails
      }
    };

    void rotateAndLog();
    const id = window.setInterval(() => {
      void rotateAndLog();
    }, 30000);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [conversationId, enabled, peerEmail, peerName, userEmail, userId]);

  const watermarkText = useMemo(() => {
    const user = normalizeEmail(userEmail) || userId || "unknown";
    const peer = peerName || shortConversationId(conversationId);
    const time = formatTimestamp(now);
    return `CurveEd25519 • ${user} • ${peer} • ${time} • ${traceCode}`;
  }, [conversationId, now, peerName, traceCode, userEmail, userId]);

  if (!enabled) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-10 overflow-hidden select-none" aria-hidden>
      <div className="absolute inset-0 rotate-[-18deg]">
        <div className="grid h-full w-full grid-cols-3 gap-8 p-8 md:grid-cols-4">
          {Array.from({ length: 18 }).map((_, idx) => (
            <span key={idx} className="text-[12px] font-bold tracking-[0.14em] text-white/20 drop-shadow-[0_0_2px_rgba(0,0,0,0.75)]">
              {watermarkText}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
