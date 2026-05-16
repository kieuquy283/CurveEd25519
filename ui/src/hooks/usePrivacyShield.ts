"use client";

import { useCallback, useEffect, useState } from "react";
import { useSettingsStore } from "@/store/useSettingsStore";

export function usePrivacyShield() {
  const prefs = useSettingsStore((s) => s.prefs);
  const [shieldActive, setShieldActive] = useState(false);

  const showShield = useCallback(() => {
    setShieldActive(true);
  }, []);

  const hideShield = useCallback(() => {
    setShieldActive(false);
  }, []);

  useEffect(() => {
    const onBlur = () => {
      if (prefs.privacyShieldEnabled && prefs.shieldOnBlur) {
        setShieldActive(true);
      }
    };

    const onVisibility = () => {
      if (document.visibilityState === "hidden" && prefs.privacyShieldEnabled && prefs.shieldOnBlur) {
        setShieldActive(true);
      }
    };

    const onFocus = () => {
      // Optional behavior: auto-hide shield shortly after focus returns.
      if (prefs.privacyShieldEnabled && prefs.shieldOnBlur) {
        window.setTimeout(() => {
          setShieldActive(false);
        }, 500);
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const isPrintScreen = event.key === "PrintScreen";
      const isShortcut =
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey &&
        event.key.toLowerCase() === "s";

      if (!prefs.privacyShieldEnabled) return;

      if ((isPrintScreen && prefs.shieldOnPrintScreen) || isShortcut) {
        setShieldActive(true);
      }

      if (isPrintScreen) {
        navigator.clipboard?.writeText("").catch(() => {
          // Best-effort only; permission can be denied.
        });
      }
    };

    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("keydown", onKeyDown);

    return () => {
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [prefs.privacyShieldEnabled, prefs.shieldOnBlur, prefs.shieldOnPrintScreen]);

  return {
    shieldActive,
    showShield,
    hideShield,
    shieldMode: prefs.shieldMode,
  };
}
