"use client";

import React from "react";
import { ChatLayout } from "@/components/ChatLayout";
import { useAuthStore } from "@/store/useAuthStore";
import { WebSocketProvider } from "@/providers/WebSocketProvider";
import AuthScreen from "@/components/auth/AuthScreen";

export default function Home() {
  const { currentUser, isAuthenticated } = useAuthStore();

  if (!isAuthenticated || !currentUser) {
    return <AuthScreen />;
  }

  return (
    <WebSocketProvider>
      <ChatLayout />
    </WebSocketProvider>
  );
}
