"use client";

import React, { useEffect, useId, useMemo, useState } from "react";
import { createPortal } from "react-dom";

type GlobalModalProps = {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  closeOnBackdrop?: boolean;
};

const sizeMap: Record<NonNullable<GlobalModalProps["size"]>, string> = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-3xl",
  xl: "max-w-5xl",
};

export default function GlobalModal({
  open,
  onClose,
  title,
  description,
  children,
  size = "md",
  closeOnBackdrop = true,
}: GlobalModalProps) {
  const [mounted, setMounted] = useState(false);
  const headingId = useId();
  const descId = useId();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const maxWidthClass = useMemo(() => sizeMap[size], [size]);

  if (!open || !mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close modal backdrop"
        className="absolute inset-0 bg-slate-950/75 backdrop-blur-sm"
        onClick={() => {
          if (closeOnBackdrop) onClose();
        }}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? headingId : undefined}
        aria-describedby={description ? descId : undefined}
        className={`relative z-10 max-h-[85vh] w-[calc(100vw-2rem)] overflow-y-auto rounded-[2rem] border border-white/10 bg-slate-950/90 text-zinc-100 shadow-[0_0_80px_rgba(79,70,229,0.35)] backdrop-blur-xl ${maxWidthClass}`}
        onClick={(event) => event.stopPropagation()}
      >
        {title ? <h2 id={headingId} className="sr-only">{title}</h2> : null}
        {description ? <p id={descId} className="sr-only">{description}</p> : null}
        {children}
      </div>
    </div>,
    document.body
  );
}
