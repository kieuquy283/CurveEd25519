"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const HIDE_ALL_EVENT = "curveapp:privacy-hide-all";

export function dispatchPrivacyHideAll() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(HIDE_ALL_EVENT));
}

export function usePrivacyReveal(messageId: string, autoHideMs: number) {
  const [revealed, setRevealed] = useState(false);
  const timerRef = useRef<number | null>(null);
  void messageId;

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const hide = useCallback(() => {
    clearTimer();
    setRevealed(false);
  }, [clearTimer]);

  const reveal = useCallback(() => {
    clearTimer();
    setRevealed(true);
    const hideDelayMs = Math.min(5000, Math.max(3000, autoHideMs));
    timerRef.current = window.setTimeout(() => {
      setRevealed(false);
      timerRef.current = null;
    }, hideDelayMs);
  }, [autoHideMs, clearTimer]);

  useEffect(() => {
    const onHideAll = () => hide();
    window.addEventListener(HIDE_ALL_EVENT, onHideAll);
    return () => {
      window.removeEventListener(HIDE_ALL_EVENT, onHideAll);
      clearTimer();
    };
  }, [hide, clearTimer]);

  return { revealed, reveal, hide };
}
