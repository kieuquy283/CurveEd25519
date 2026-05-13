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
  upsertConversation: (conversation: Conversation) => void;
  updateConversationPreview: (conversationId: string, preview: string, createdAt: string) => void;
  markConversationUnread: (conversationId: string) => void;
  markConversationRead: (conversationId: string) => void;

  // Message methods
  addMessage: (message: ChatMessage) => void;
  appendMessage: (conversationId: string, message: ChatMessage) => void;
  addMessages: (messages: ChatMessage[]) => void;
  replaceMessage: (conversationId: string, tempId: string, realMessage: ChatMessage) => void;
  dedupeMessages: (conversationId: string) => void;
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

function messageDedupKey(message: ChatMessage): string {
  const envelope = message.envelope as Record<string, unknown> | undefined;
  const envelopeMessageId =
    envelope && typeof envelope.message_id === "string" ? envelope.message_id : "";
  if (message.id) return `id:${message.id}`;
  if (message.packetId) return `packet:${message.packetId}`;
  if (message.clientMessageId) return `client:${message.clientMessageId}`;
  if (envelopeMessageId) return `env:${envelopeMessageId}`;
  return `fallback:${message.from}:${message.to}:${message.timestamp}:${message.text.slice(0, 64)}`;
}

function upsertMessageList(existing: ChatMessage[], incoming: ChatMessage): ChatMessage[] {
  const incomingKeys = new Set([
    messageDedupKey(incoming),
    incoming.packetId ? `packet:${incoming.packetId}` : "",
    incoming.clientMessageId ? `client:${incoming.clientMessageId}` : "",
  ].filter(Boolean));

  const index = existing.findIndex((m) => {
    const keys = [
      messageDedupKey(m),
      m.packetId ? `packet:${m.packetId}` : "",
      m.clientMessageId ? `client:${m.clientMessageId}` : "",
    ];
    return keys.some((k) => k && incomingKeys.has(k));
  });

  if (index >= 0) {
    const next = [...existing];
    next[index] = { ...next[index], ...incoming };
    return next;
  }
  return [...existing, incoming];
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
      upsertConversation: (conversation) =>
        get().addConversation(conversation),

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
      markConversationUnread: (conversationId) =>
        set((state) => {
          const newConversations = new Map(state.conversations);
          const conversation = newConversations.get(conversationId);
          if (!conversation) return { conversations: newConversations };
          newConversations.set(conversationId, {
            ...conversation,
            unreadCount: (conversation.unreadCount ?? 0) + 1,
          });
          return { conversations: newConversations };
        }),
      markConversationRead: (conversationId) => get().clearUnreadCount(conversationId),
      updateConversationPreview: (conversationId, preview, createdAt) =>
        set((state) => {
          const newConversations = new Map(state.conversations);
          const conversation = newConversations.get(conversationId);
          if (!conversation) return { conversations: newConversations };
          newConversations.set(conversationId, {
            ...conversation,
            lastMessageAt: createdAt,
            lastMessage: {
              id: `preview-${conversationId}-${createdAt}`,
              conversationId,
              from: conversation.peerId,
              to: "",
              text: preview,
              timestamp: createdAt,
              status: "delivered",
              type: "text",
            },
          });
          return { conversations: newConversations };
        }),

      addMessage: (message) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          const newConversations = new Map(state.conversations);
          const convMessages = newMessages.get(message.conversationId) || [];
          newMessages.set(message.conversationId, upsertMessageList(convMessages, message));

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
      appendMessage: (conversationId, message) =>
        get().addMessage({
          ...message,
          conversationId,
        }),

      addMessages: (messagesToAdd) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          const newConversations = new Map(state.conversations);

          for (const message of messagesToAdd) {
            const convMessages = newMessages.get(message.conversationId) || [];
            newMessages.set(message.conversationId, upsertMessageList(convMessages, message));

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
      replaceMessage: (conversationId, tempId, realMessage) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          const convMessages = newMessages.get(conversationId) || [];
          const next = convMessages.map((message) =>
            message.id === tempId || (realMessage.clientMessageId && message.clientMessageId === realMessage.clientMessageId)
              ? { ...message, ...realMessage, id: realMessage.id }
              : message
          );
          newMessages.set(conversationId, upsertMessageList(next, realMessage));
          return { messages: newMessages };
        }),
      dedupeMessages: (conversationId) =>
        set((state) => {
          const newMessages = new Map(state.messages);
          const convMessages = newMessages.get(conversationId) || [];
          const seen = new Set<string>();
          const deduped: ChatMessage[] = [];
          for (const message of convMessages) {
            const key = messageDedupKey(message);
            if (seen.has(key)) continue;
            seen.add(key);
            deduped.push(message);
          }
          newMessages.set(conversationId, deduped);
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
