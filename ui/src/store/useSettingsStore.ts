/**
 * Settings store with local persistence.
 */
import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { UiPreferences } from "@/types/models";
import { getWsUrl } from "@/config/env";

export interface SettingsState {
  prefs: UiPreferences;

  setPrefs: (partial: Partial<UiPreferences>) => void;
  setTheme: (theme: UiPreferences["theme"]) => void;
  setWsEndpoint: (url: string) => void;
  reset: () => void;
}

const DEFAULT_PREFS: UiPreferences = {
  theme: "dark",
  fontSize: "md",
  compactMode: false,
  enableSound: true,
  enableDesktopNotifications: false,
  enableTypingIndicators: true,
  enableReadReceipts: true,
  wsEndpoint: getWsUrl(),
  localPeerId:
    process.env.NEXT_PUBLIC_USER_ID ||
    "frontend",
};

const STORAGE_KEY = "mmatt_settings_v1";

function loadPrefs(): Partial<UiPreferences> | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return undefined;
    return JSON.parse(raw) as Partial<UiPreferences>;
  } catch {
    return undefined;
  }
}

export const useSettingsStore = create<SettingsState>()(
  devtools((set, get) => {
    const persisted = loadPrefs();
    const initial: UiPreferences = { ...DEFAULT_PREFS, ...(persisted ?? {}) };

    // subscribe to save
    if (typeof window !== "undefined") {
      // persist whenever prefs change
      const unsub = () => {
        /* placeholder for devtools compatibility */
      };
      // we will attach a proper subscription after store creation below
    }

    return {
      prefs: initial,

      setPrefs: (partial) =>
        set((state) => ({ prefs: { ...state.prefs, ...partial } })),

      setTheme: (theme) => set((state) => ({ prefs: { ...state.prefs, theme } })),

      setWsEndpoint: (url) => set((state) => ({ prefs: { ...state.prefs, wsEndpoint: url } })),

      reset: () => set({ prefs: DEFAULT_PREFS }),
    };
  }, { name: "SettingsStore" })
);

// persist subscription (client-only)
if (typeof window !== "undefined") {
  useSettingsStore.subscribe((state) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.prefs));
    } catch {
      // ignore
    }
  });
}

