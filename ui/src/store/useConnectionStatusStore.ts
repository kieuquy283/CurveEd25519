import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { ConnectionStatusResponse, getConnectionStatus, makeConnectionPairKey, normalizeEmail } from "@/services/connections";

type ConnectionStatusStore = {
  connectionStatusByPair: Record<string, ConnectionStatusResponse>;
  loadingByPair: Record<string, boolean>;
  errorByPair: Record<string, string | null>;
  setConnectionStatus: (userEmail: string, peerEmail: string, status: ConnectionStatusResponse) => void;
  getConnectionStatusForPair: (userEmail: string, peerEmail: string) => ConnectionStatusResponse | null;
  refreshConnectionStatus: (userEmail: string, peerIdentifier: string) => Promise<ConnectionStatusResponse>;
  clearForUser: (userEmail: string) => void;
};

export const useConnectionStatusStore = create<ConnectionStatusStore>()(
  devtools((set, get) => ({
    connectionStatusByPair: {},
    loadingByPair: {},
    errorByPair: {},

    setConnectionStatus: (userEmail, peerEmail, status) => {
      const pairKey = makeConnectionPairKey(userEmail, peerEmail);
      set((state) => ({
        connectionStatusByPair: { ...state.connectionStatusByPair, [pairKey]: status },
        loadingByPair: { ...state.loadingByPair, [pairKey]: false },
        errorByPair: { ...state.errorByPair, [pairKey]: null },
      }));
    },

    getConnectionStatusForPair: (userEmail, peerEmail) => {
      const pairKey = makeConnectionPairKey(userEmail, peerEmail);
      return get().connectionStatusByPair[pairKey] ?? null;
    },

    refreshConnectionStatus: async (userEmail, peerIdentifier) => {
      const user = normalizeEmail(userEmail);
      const peer = normalizeEmail(peerIdentifier);
      const pairKeySeed = makeConnectionPairKey(user, peer);

      set((state) => ({
        loadingByPair: { ...state.loadingByPair, [pairKeySeed]: true },
        errorByPair: { ...state.errorByPair, [pairKeySeed]: null },
      }));

      try {
        const status = await getConnectionStatus(user, peerIdentifier);
        const canonicalUser = normalizeEmail(status.user?.email || user);
        const canonicalPeer = normalizeEmail(status.peer?.email || peerIdentifier);
        const pairKey = makeConnectionPairKey(canonicalUser, canonicalPeer);

        set((state) => ({
          connectionStatusByPair: { ...state.connectionStatusByPair, [pairKey]: status },
          loadingByPair: { ...state.loadingByPair, [pairKey]: false, [pairKeySeed]: false },
          errorByPair: { ...state.errorByPair, [pairKey]: null, [pairKeySeed]: null },
        }));

        return status;
      } catch (error) {
        const msg = error instanceof Error ? error.message : "refresh_connection_status_failed";
        set((state) => ({
          loadingByPair: { ...state.loadingByPair, [pairKeySeed]: false },
          errorByPair: { ...state.errorByPair, [pairKeySeed]: msg },
        }));
        throw error;
      }
    },

    clearForUser: (userEmail) => {
      const target = normalizeEmail(userEmail);
      set((state) => {
        const nextStatus: Record<string, ConnectionStatusResponse> = {};
        const nextLoading: Record<string, boolean> = {};
        const nextError: Record<string, string | null> = {};

        for (const [key, value] of Object.entries(state.connectionStatusByPair)) {
          if (!key.includes(target)) nextStatus[key] = value;
        }
        for (const [key, value] of Object.entries(state.loadingByPair)) {
          if (!key.includes(target)) nextLoading[key] = value;
        }
        for (const [key, value] of Object.entries(state.errorByPair)) {
          if (!key.includes(target)) nextError[key] = value;
        }

        return {
          connectionStatusByPair: nextStatus,
          loadingByPair: nextLoading,
          errorByPair: nextError,
        };
      });
    },
  }), { name: "ConnectionStatusStore" })
);
