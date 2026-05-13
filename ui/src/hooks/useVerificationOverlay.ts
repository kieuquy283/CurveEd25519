"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type OverlayState = {
  open: boolean;
  status: "verified" | "failed";
  title?: string;
  message?: string;
};

const DEFAULT_OVERLAY: OverlayState = {
  open: false,
  status: "verified",
};

export function useVerificationOverlay(autoHideMs = 1500) {
  const [overlay, setOverlay] = useState<OverlayState>(DEFAULT_OVERLAY);
  const timeoutRef = useRef<number | null>(null);

  const clearOverlayTimeout = useCallback(() => {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const hide = useCallback(() => {
    clearOverlayTimeout();
    setOverlay((prev) => ({ ...prev, open: false }));
  }, [clearOverlayTimeout]);

  const show = useCallback(
    (status: "verified" | "failed", title?: string, message?: string) => {
      clearOverlayTimeout();
      setOverlay({
        open: true,
        status,
        title,
        message,
      });
      timeoutRef.current = window.setTimeout(() => {
        setOverlay((prev) => ({ ...prev, open: false }));
        timeoutRef.current = null;
      }, autoHideMs);
    },
    [autoHideMs, clearOverlayTimeout]
  );

  const showVerified = useCallback((message?: string, title?: string) => {
    show("verified", title, message);
  }, [show]);

  const showFailed = useCallback((message?: string, title?: string) => {
    show("failed", title, message);
  }, [show]);

  useEffect(() => {
    return () => clearOverlayTimeout();
  }, [clearOverlayTimeout]);

  return { overlay, showVerified, showFailed, hide };
}

