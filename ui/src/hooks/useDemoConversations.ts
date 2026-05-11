/**
 * Hook to initialize demo conversations for testing.
 */

import { useEffect } from "react";
import { useChatStore } from "@/store/useChatStore";
import { Conversation, ChatMessage } from "@/types/models";

export function useDemoConversations() {
  useEffect(() => {
    const chatStore = useChatStore.getState();

    // Create demo conversations
    const demoConversations: Conversation[] = [
      {
        id: "conv-alice",
        peerId: "alice",
        peerName: "Alice",
        unreadCount: 3,
        isOnline: true,
        isMuted: false,
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 7).toISOString(),
        lastMessageAt: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      },
      {
        id: "conv-bob",
        peerId: "bob",
        peerName: "Bob",
        unreadCount: 0,
        isOnline: false,
        isMuted: false,
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(),
        lastMessageAt: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
      },
      {
        id: "conv-celia",
        peerId: "celia",
        peerName: "Celia",
        unreadCount: 1,
        isOnline: true,
        isMuted: false,
        createdAt: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
        lastMessageAt: new Date(Date.now() - 1000 * 60 * 10).toISOString(),
      },
    ];

    // Create demo messages
    const demoMessages: ChatMessage[] = [
      // Alice messages
      {
        id: "msg-alice-1",
        conversationId: "conv-alice",
        from: "alice",
        to: "frontend",
        text: "Hey! How are you doing?",
        timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
        status: "delivered",
      },
      {
        id: "msg-alice-2",
        conversationId: "conv-alice",
        from: "frontend",
        to: "alice",
        text: "I'm doing great, thanks for asking!",
        timestamp: new Date(Date.now() - 1000 * 60 * 25).toISOString(),
        status: "read",
      },
      {
        id: "msg-alice-3",
        conversationId: "conv-alice",
        from: "alice",
        to: "frontend",
        text: "That's great to hear 😊",
        timestamp: new Date(Date.now() - 1000 * 60 * 20).toISOString(),
        status: "delivered",
      },
      {
        id: "msg-alice-4",
        conversationId: "conv-alice",
        from: "alice",
        to: "frontend",
        text: "Want to grab coffee later?",
        timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
        status: "delivered",
      },

      // Bob messages
      {
        id: "msg-bob-1",
        conversationId: "conv-bob",
        from: "bob",
        to: "frontend",
        text: "Meeting at 3 PM tomorrow",
        timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
        status: "read",
      },

      // Celia messages
      {
        id: "msg-celia-1",
        conversationId: "conv-celia",
        from: "frontend",
        to: "celia",
        text: "Thanks for the file you sent",
        timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
        status: "delivered",
      },
      {
        id: "msg-celia-2",
        conversationId: "conv-celia",
        from: "celia",
        to: "frontend",
        text: "You're welcome! Let me know if you need anything else",
        timestamp: new Date(Date.now() - 1000 * 60 * 10).toISOString(),
        status: "delivered",
      },
    ];

    // Add to store
    demoConversations.forEach((conv) => {
      chatStore.addConversation(conv);
    });

    demoMessages.forEach((msg) => {
      chatStore.addMessage(msg);
    });

    // Set first conversation as active
    if (demoConversations.length > 0) {
      chatStore.setActiveConversation(demoConversations[0].id);
    }
  }, []);
}
