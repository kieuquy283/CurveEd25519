/**
 * Trust state store — manages trust/fingerprint info per peer.
 */
import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { TrustLevel } from "@/types/models";

export interface TrustEntry {
  peerId: string;
  fingerprint?: string;
  trustLevel: TrustLevel;
  verifiedAt?: number;
}

interface TrustStore {
  entries: Map<string, TrustEntry>;
  setTrustEntry: (entry: TrustEntry) => void;
  updateTrustLevel: (peerId: string, trustLevel: TrustLevel) => void;
  getEntry: (peerId: string) => TrustEntry | undefined;
  removeEntry: (peerId: string) => void;
  reset: () => void;
}

export const useTrustStore = create<TrustStore>()(
  devtools((set, get) => ({
    entries: new Map(),

    setTrustEntry: (entry) =>
      set((state) => {
        const m = new Map(state.entries);
        m.set(entry.peerId, entry);
        return { entries: m };
      }),

    updateTrustLevel: (peerId, trustLevel) =>
      set((state) => {
        const m = new Map(state.entries);
        const existing = m.get(peerId);
        if (existing) {
          m.set(peerId, { ...existing, trustLevel, verifiedAt: Date.now() });
        } else {
          m.set(peerId, { peerId, trustLevel, verifiedAt: Date.now() });
        }
        return { entries: m };
      }),

    getEntry: (peerId) => get().entries.get(peerId),

    removeEntry: (peerId) =>
      set((state) => {
        const m = new Map(state.entries);
        m.delete(peerId);
        return { entries: m };
      }),

    reset: () => set({ entries: new Map() }),
  }), { name: "TrustStore" })
);
