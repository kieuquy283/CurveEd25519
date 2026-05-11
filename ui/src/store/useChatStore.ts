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
  updateMessageCrypto: (
    messageId: string,
    conversationId: string,
    crypto: Partial<ChatMessage>
  ) => void;
  updateMessage: (
    messageId: string,
    conversationId: string,
    partial: Partial<ChatMessage>
  ) => void;
  clearMessages: (conversationId: string) => void;

  // Utility methods
  reset: () => void;
}

function sortConversations(conversations: Conversation[]) {
  return conversations.sort(
    (a, b) =>
      new Date(b.lastMessageAt || b.createdAt).getTime() -
      new Date(a.lastMessageAt || a.createdAt).getTime()
  );
}

function touchConversation(
  conversations: Map<string, Conversation>,
  conversationId: string,
  timestamp?: string
) {
  const existing = conversations.get(conversationId);

  if (!existing) {
    return conversations;
  }

  conversations.set(conversationId, {
    ...existing,
    lastMessageAt: timestamp || existing.lastMessageAt || existing.createdAt,
  });

  return conversations;
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
          const existing = newConversations.get(conversation.id);

          newConversations.set(conversation.id, {
            ...existing,
            ...conversation,
          });

          return {
            conversations: newConversations,
          };
        }),

      updateConversation: (id, partial) =>
        set((state) => {
          const newConversations = new Map(state.conversations);
          const existing = newConversations.get(id);

          if (existing) {
            newConversations.set(id, {
              ...existing,
              ...partial,
            });
          }

          return {
            conversations: newConversations,
          };
        }),

      removeConversation: (id) =>
        set((state) => {
          const newConversations = new Map(state.conversations);
          const newMessages = new Map(state.messages);

          newConversations.delete(id);
          newMessages.delete(id);

          return {
            conversations: newConversations,
            messages: newMessages,
            activeConversationId:
              state.activeConversationId === id
                ? null
                : state.activeConversationId,
          };
        }),

      getConversations: () => {
        const state = get();

        return sortConversations(
          Array.from(state.conversations.values())
        );
      },

      setActiveConversation: (id) =>
        set({
          activeConversationId: id,
        }),

      clearUnreadCount: (conversationId) =>
        set((state) => {
          const newConversations = new Map(state.conversations);
          const conversation = newConversations.get(conversationId);

          if (conversation) {
            newConversations.set(conversationId, {
              ...conversation,
              unreadCount: 0,
            });
          }

          return {
            conversations: newConversations,
          };
        }),

      addMessage: (message) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          const newConversations = new Map(state.conversations);

          const convMessages =
            newMessages.get(message.conversationId) || [];

          const exists = convMessages.some((m) => m.id === message.id);

          if (!exists) {
            newMessages.set(message.conversationId, [
              ...convMessages,
              message,
            ]);
          }

          touchConversation(
            newConversations,
            message.conversationId,
            message.timestamp
          );

          return {
            messages: newMessages,
            conversations: newConversations,
          };
        }),

      addMessages: (messagesToAdd) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          const newConversations = new Map(state.conversations);

          for (const message of messagesToAdd) {
            const convMessages =
              newMessages.get(message.conversationId) || [];

            const exists = convMessages.some((m) => m.id === message.id);

            if (!exists) {
              newMessages.set(message.conversationId, [
                ...convMessages,
                message,
              ]);
            }

            touchConversation(
              newConversations,
              message.conversationId,
              message.timestamp
            );
          }

          return {
            messages: newMessages,
            conversations: newConversations,
          };
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
            convMessages.map((message) =>
              message.id === messageId
                ? {
                    ...message,
                    status,
                  }
                : message
            )
          );

          return {
            messages: newMessages,
          };
        }),

      updateMessageCrypto: (messageId, conversationId, crypto) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          const convMessages = newMessages.get(conversationId) || [];

          newMessages.set(
            conversationId,
            convMessages.map((message) =>
              message.id === messageId
                ? {
                    ...message,
                    ...crypto,
                  }
                : message
            )
          );

          return {
            messages: newMessages,
          };
        }),

      updateMessage: (messageId, conversationId, partial) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          const convMessages = newMessages.get(conversationId) || [];

          newMessages.set(
            conversationId,
            convMessages.map((message) =>
              message.id === messageId
                ? {
                    ...message,
                    ...partial,
                  }
                : message
            )
          );

          return {
            messages: newMessages,
          };
        }),

      clearMessages: (conversationId) =>
        set((state) => {
          const newMessages = new Map(state.messages);

          newMessages.delete(conversationId);

          return {
            messages: newMessages,
          };
        }),

      reset: () =>
        set({
          conversations: new Map(),
          messages: new Map(),
          activeConversationId: null,
        }),
    }),
    {
      name: "ChatStore",
    }
  )
);