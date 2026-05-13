"use client";

import React, { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, XCircle } from "lucide-react";

type VerificationResultOverlayProps = {
  open: boolean;
  status: "verified" | "failed";
  title?: string;
  message?: string;
};

export default function VerificationResultOverlay({
  open,
  status,
  title,
  message,
}: VerificationResultOverlayProps) {
  const [mounted, setMounted] = useState(false);
  const titleId = useId();

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  if (!mounted || !open) return null;

  const isVerified = status === "verified";
  const resolvedTitle = title ?? (isVerified ? "Verified" : "Not verified");
  const resolvedMessage = message ?? (isVerified ? "Chữ ký hợp lệ" : "Chữ ký không hợp lệ");

  return createPortal(
    <div className="pointer-events-none fixed inset-0 z-[10000] flex items-center justify-center p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`min-w-[220px] rounded-[2rem] border bg-slate-950/90 px-8 py-7 text-center text-zinc-100 backdrop-blur-xl transition-all duration-200 ${
          isVerified
            ? "border-emerald-400/30 shadow-[0_0_60px_rgba(16,185,129,0.35)]"
            : "border-rose-400/30 shadow-[0_0_60px_rgba(244,63,94,0.35)]"
        }`}
      >
        <div
          className={`mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full ${
            isVerified ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"
          }`}
        >
          {isVerified ? <CheckCircle2 size={30} /> : <XCircle size={30} />}
        </div>
        <div id={titleId} className="text-xl font-semibold">
          {resolvedTitle}
        </div>
        <div className="mt-1 text-sm text-zinc-300">{resolvedMessage}</div>
      </div>
    </div>,
    document.body
  );
}
