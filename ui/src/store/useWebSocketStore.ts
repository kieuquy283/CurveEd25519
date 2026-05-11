/**
 * Consolidated WebSocket + transport state store.
 * Single source of truth — useWsStore.ts re-exports from here.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { WebSocketState } from "@/types/models";

interface WebSocketStore extends WebSocketState {
  setConnected: (connected: boolean) => void;
  setConnecting: (connecting: boolean) => void;
  setError: (error: string | null) => void;
  setReconnectAttempts: (attempts: number) => void;
  setLastConnectedAt: (time: string) => void;
  reset: () => void;
}

const initialState: WebSocketState = {
  connected: false,
  connecting: false,
  error: null,
  reconnectAttempts: 0,
  lastConnectedAt: undefined,
};

export const useWebSocketStore = create<WebSocketStore>()(
  devtools(
    (set) => ({
      ...initialState,
      setConnected: (connected) => set({ connected, connecting: false }),
      setConnecting: (connecting) => set({ connecting }),
      setError: (error) => set({ error }),
      setReconnectAttempts: (reconnectAttempts) => set({ reconnectAttempts }),
      setLastConnectedAt: (lastConnectedAt) => set({ lastConnectedAt }),
      reset: () => set(initialState),
    }),
    { name: "WebSocketStore" }
  )
);
