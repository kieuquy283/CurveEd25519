/**
 * Typing indicator state store.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { TypingState } from "@/types/models";

interface TypingStore {
  typingPeers: Map<string, TypingState>;
  isLocalTyping: Map<string, boolean>;
  
  setTyping: (peerId: string, isTyping: boolean) => void;
  setRemoteTyping: (peerId: string, isTyping: boolean) => void;
  getTypingPeers: (conversationId: string) => string[];
  clearTypingPeer: (peerId: string) => void;
  reset: () => void;
}

export const useTypingStore = create<TypingStore>()(
  devtools(
    (set, get) => ({
      typingPeers: new Map(),
      isLocalTyping: new Map(),
      
      setTyping: (peerId, isTyping) =>
        set((state) => {
          const newLocal = new Map(state.isLocalTyping);
          newLocal.set(peerId, isTyping);
          return { isLocalTyping: newLocal };
        }),
      
      setRemoteTyping: (peerId, isTyping) =>
        set((state) => {
          const newTyping = new Map(state.typingPeers);
          if (isTyping) {
            newTyping.set(peerId, {
              peerId,
              isTyping: true,
              startedAt: Date.now(),
              expiresAt: Date.now() + 5000, // 5s timeout
            });
          } else {
            newTyping.delete(peerId);
          }
          return { typingPeers: newTyping };
        }),
      
      getTypingPeers: (conversationId) => {
        const state = get();
        const now = Date.now();
        const peers: string[] = [];
        
        state.typingPeers.forEach((typing, peerId) => {
          if (now < typing.expiresAt) {
            peers.push(peerId);
          }
        });
        
        return peers;
      },
      
      clearTypingPeer: (peerId) =>
        set((state) => {
          const newTyping = new Map(state.typingPeers);
          newTyping.delete(peerId);
          return { typingPeers: newTyping };
        }),
      
      reset: () => set({ typingPeers: new Map(), isLocalTyping: new Map() }),
    }),
    { name: "TypingStore" }
  )
);
