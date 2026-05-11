/**
 * Settings persistence helpers.
 */
import { UiPreferences } from "@/types/models";

const KEY = "mmatt_settings_v1";

export function loadSettings(): Partial<UiPreferences> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    return JSON.parse(raw) as Partial<UiPreferences>;
  } catch {
    return null;
  }
}

export function saveSettings(prefs: Partial<UiPreferences>): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    // noop
  }
}
