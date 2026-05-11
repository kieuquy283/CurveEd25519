"use client";
import React from "react";
import TypingIndicator from "./TypingIndicator";

interface Props {
  children?: React.ReactNode;
}

const ChatContainer: React.FC<Props> = ({ children }) => (
  <main className="flex-1 flex flex-col bg-gradient-to-b from-slate-900 to-slate-800">
    <div className="flex-1 overflow-auto p-4">
      {children ?? <div className="text-slate-400">Select a conversation to start chatting.</div>}
    </div>

    <div className="border-t border-slate-700">
      <TypingIndicator />
      <div className="p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-2">
            <input
              placeholder="Message"
              className="flex-1 bg-slate-700 rounded-md px-3 py-2 focus:outline-none"
            />
            <button className="ml-2 bg-indigo-600 hover:bg-indigo-500 rounded-md px-3 py-2">Send</button>
          </div>
        </div>
      </div>
    </div>
  </main>
);

export default ChatContainer;
