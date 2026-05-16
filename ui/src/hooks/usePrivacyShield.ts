"use client";

import { useCallback, useEffect, useState } from "react";
import { useSettingsStore } from "@/store/useSettingsStore";

export function usePrivacyShield() {
  const prefs = useSettingsStore((s) => s.prefs);
  const [shieldActive, setShieldActive] = useState(false);

  const showShield = useCallback((_reason?: string) => {
    setShieldActive(true);
  }, []);

  const hideShield = useCallback(() => {
    setShieldActive(false);
  }, []);

  useEffect(() => {
    const onBlur = () => {
      if (prefs.privacyShieldEnabled && prefs.shieldOnBlur) {
        showShield("blur");
      }
    };

    const onFocusOut = () => {
      if (prefs.privacyShieldEnabled && prefs.shieldOnBlur) {
        showShield("focusout");
      }
    };

    const onVisibility = () => {
      if (document.visibilityState === "hidden" && prefs.privacyShieldEnabled && prefs.shieldOnBlur) {
        showShield("visibility_hidden");
      }
    };

    const onPageHide = () => {
      if (prefs.privacyShieldEnabled && prefs.shieldOnBlur) {
        showShield("pagehide");
      }
    };

    const onFreeze = () => {
      if (prefs.privacyShieldEnabled && prefs.shieldOnBlur) {
        showShield("freeze");
      }
    };

    const onFocus = () => {
      if (
        prefs.privacyShieldEnabled &&
        prefs.shieldOnBlur &&
        !prefs.shieldPersistUntilUnlock &&
        shieldActive
      ) {
        window.setTimeout(() => {
          setShieldActive(false);
        }, 500);
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const key = event.key || "";
      const code = event.code || "";
      const metaPressed = event.metaKey || event.getModifierState?.("Meta");
      const isPrintScreen = key === "PrintScreen" || code === "PrintScreen";
      const isMetaShiftS =
        Boolean(metaPressed) &&
        event.shiftKey &&
        (code === "KeyS" || key.toLowerCase() === "s");

      if (!prefs.privacyShieldEnabled) return;

      if ((isPrintScreen && prefs.shieldOnPrintScreen) || isMetaShiftS) {
        showShield("screenshot_shortcut");
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation?.();
      }

      if (isPrintScreen) {
        navigator.clipboard?.writeText("").catch(() => {
          // Best-effort only; permission can be denied.
        });
      }
    };

    window.addEventListener("blur", onBlur);
    window.addEventListener("focusout", onFocusOut);
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", onPageHide);
    document.addEventListener("freeze", onFreeze as EventListener);
    window.addEventListener("keydown", onKeyDown, { capture: true });

    return () => {
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focusout", onFocusOut);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", onPageHide);
      document.removeEventListener("freeze", onFreeze as EventListener);
      window.removeEventListener("keydown", onKeyDown, { capture: true });
    };
  }, [
    prefs.privacyShieldEnabled,
    prefs.shieldOnBlur,
    prefs.shieldOnPrintScreen,
    prefs.shieldPersistUntilUnlock,
    shieldActive,
    showShield,
  ]);

  return {
    shieldActive,
    showShield,
    hideShield,
    shieldMode: prefs.shieldMode,
  };
}
