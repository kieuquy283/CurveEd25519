/**
 * UI preferences and session settings store (persisted).
 */

import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import { UiPreferences } from "@/types/models";

interface UiStore extends UiPreferences {
  // Panel state
  sidebarOpen: boolean;
  settingsOpen: boolean;
  contactsOpen: boolean;

  updatePreferences: (partial: Partial<UiPreferences>) => void;
  setSidebarOpen: (open: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
  setContactsOpen: (open: boolean) => void;
  reset: () => void;
}

const defaultPreferences: UiPreferences = {
  theme: "dark",
  fontSize: "md",
  compactMode: false,
  enableSound: true,
  enableDesktopNotifications: true,
  enableTypingIndicators: true,
  enableReadReceipts: true,
  wsEndpoint: process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8765",
  localPeerId:
    process.env.NEXT_PUBLIC_USER_ID ||
    "frontend",
};

export const useUiStore = create<UiStore>()(
  devtools(
    persist(
      (set) => ({
        ...defaultPreferences,
        sidebarOpen: true,
        settingsOpen: false,
        contactsOpen: false,

        updatePreferences: (partial) => set(partial),
        setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
        setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
        setContactsOpen: (contactsOpen) => set({ contactsOpen }),
        reset: () =>
          set({ ...defaultPreferences, sidebarOpen: true, settingsOpen: false, contactsOpen: false }),
      }),
      { name: "uiPreferences", partialize: (s) => ({ ...defaultPreferences, ...s }) }
    ),
    { name: "UiStore" }
  )
);

