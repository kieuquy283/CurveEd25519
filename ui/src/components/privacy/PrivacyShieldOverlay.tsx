"use client";

import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface PrivacyShieldOverlayProps {
  active: boolean;
  mode?: "black" | "blur";
  onUnlock: () => void;
}

export default function PrivacyShieldOverlay({ active, mode = "black", onUnlock }: PrivacyShieldOverlayProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted || !active) return null;

  const toneClass = mode === "blur" ? "bg-black backdrop-blur-xl" : "bg-black";

  return createPortal(
    <div
      className={`fixed inset-0 z-[2147483647] ${toneClass} pointer-events-auto select-none flex items-center justify-center p-6`}
      role="dialog"
      aria-modal="true"
    >
      <div className="text-center">
        <div className="text-lg font-semibold tracking-wide text-zinc-100">CurveEd25519</div>
        <div className="mt-2 text-sm text-zinc-300">Nội dung đang được bảo vệ</div>
        <button
          type="button"
          onClick={onUnlock}
          className="mt-6 rounded-2xl border border-white/15 bg-white/10 px-4 py-2 text-sm text-white transition hover:bg-white/20"
        >
          Hiện lại
        </button>
      </div>
    </div>,
    document.body
  );
}
