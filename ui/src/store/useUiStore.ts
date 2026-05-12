/**
 * UI preferences and session settings store (persisted).
 */

import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import { UiPreferences } from "@/types/models";
import { getWsUrl } from "@/config/env";

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
  fontFamily: "default",
  compactMode: false,
  enableSound: true,
  enableDesktopNotifications: true,
  enableTypingIndicators: true,
  enableReadReceipts: true,
  wsEndpoint: getWsUrl(),
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

