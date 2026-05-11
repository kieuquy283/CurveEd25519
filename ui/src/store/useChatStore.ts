/**
 * Chat state store for messages and conversations.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { ChatMessage, Conversation } from "@/types/models";

interface ChatStore {
  conversations: Map<string, Conversation>;
  messages: Map<string, ChatMessage[]>;
  activeConversationId: string | null;
  
  // Conversation methods
  addConversation: (conversation: Conversation) => void;
  updateConversation: (id: string, partial: Partial<Conversation>) => void;
  removeConversation: (id: string) => void;
  getConversations: () => Conversation[];
  setActiveConversation: (id: string | null) => void;
  clearUnreadCount: (conversationId: string) => void;
  
  // Message methods
  addMessage: (message: ChatMessage) => void;
  addMessages: (messages: ChatMessage[]) => void;
  getMessages: (conversationId: string) => ChatMessage[];
  updateMessageStatus: (
    messageId: string,
    conversationId: string,
    status: ChatMessage["status"]
  ) => void;
  clearMessages: (conversationId: string) => void;
  
  // Utility methods
  reset: () => void;
}

export const useChatStore = create<ChatStore>()(
  devtools(
    (set, get) => ({
      conversations: new Map(),
      messages: new Map(),
      activeConversationId: null,
      
      addConversation: (conversation) =>
        set((state) => {
          const newConversations = new Map(state.conversations);
          newConversations.set(conversation.id, conversation);
          return { conversations: newConversations };
        }),
      
      updateConversation: (id, partial) =>
        set((state) => {
          const newConversations = new Map(state.conversations);
          const existing = newConversations.get(id);
          if (existing) {
            newConversations.set(id, { ...existing, ...partial });
          }
          return { conversations: newConversations };
        }),
      
      removeConversation: (id) =>
        set((state) => {
          const newConversations = new Map(state.conversations);
          newConversations.delete(id);
          return { conversations: newConversations };
        }),
      
      getConversations: () => {
        const state = get();
        return Array.from(state.conversations.values()).sort(
          (a, b) =>
            new Date(b.lastMessageAt || b.createdAt).getTime() -
            new Date(a.lastMessageAt || a.createdAt).getTime()
        );
      },
      
      setActiveConversation: (id) => set({ activeConversationId: id }),
      
      clearUnreadCount: (conversationId) =>
        set((state) => {
          const newConversations = new Map(state.conversations);
          const conv = newConversations.get(conversationId);
          if (conv) {
            newConversations.set(conversationId, { ...conv, unreadCount: 0 });
          }
          return { conversations: newConversations };
        }),
      
      addMessage: (message) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          const convMessages = newMessages.get(message.conversationId) || [];
          newMessages.set(message.conversationId, [...convMessages, message]);
          return { messages: newMessages };
        }),
      
      addMessages: (messagesToAdd) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          for (const message of messagesToAdd) {
            const convMessages = newMessages.get(message.conversationId) || [];
            newMessages.set(message.conversationId, [...convMessages, message]);
          }
          return { messages: newMessages };
        }),
      
      getMessages: (conversationId) => {
        const state = get();
        return state.messages.get(conversationId) || [];
      },
      
      updateMessageStatus: (messageId, conversationId, status) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          const convMessages = newMessages.get(conversationId) || [];
          newMessages.set(
            conversationId,
            convMessages.map((m) =>
              m.id === messageId ? { ...m, status } : m
            )
          );
          return { messages: newMessages };
        }),
      
      clearMessages: (conversationId) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          newMessages.delete(conversationId);
          return { messages: newMessages };
        }),
      
      reset: () => set({ conversations: new Map(), messages: new Map(), activeConversationId: null }),
    }),
    { name: "ChatStore" }
  )
);
