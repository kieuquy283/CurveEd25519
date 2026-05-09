"use client";
import ChatWindow from "@/components/ChatWindow";

export default function Home() {
  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black">
      <header className="p-4 border-b">
        <h1 className="text-lg font-semibold">CurveApp — Chat</h1>
      </header>
      <main className="p-6">
        <ChatWindow />
      </main>
    </div>
  );
}
