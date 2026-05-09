import { create } from "zustand";
import { ChatMessage } from "@/types/transport";

type State = {
  connected: boolean;
  lastError: string | null;
  messages: ChatMessage[];
  typingPeers: string[];
  addMessage: (m: ChatMessage) => void;
  setConnected: (v: boolean) => void;
  setError: (e: string | null) => void;
  setTypingPeers: (peers: string[]) => void;
};

export const useWsStore = create<State>((set) => ({
  connected: false,
  lastError: null,
  messages: [],
  typingPeers: [],
  addMessage: (m: ChatMessage) =>
    set((s) => ({ messages: [...s.messages, m] })),
  setConnected: (v: boolean) => set(() => ({ connected: v })),
  setError: (e: string | null) => set(() => ({ lastError: e })),
  setTypingPeers: (peers: string[]) => set(() => ({ typingPeers: peers })),
}));
