"use client";
import React from "react";

interface Props {
  open: boolean;
  onToggle: () => void;
}

const ChatSidebar: React.FC<Props> = ({ open, onToggle }) => {
  return (
    <aside
      aria-hidden={!open}
      className={`fixed md:relative z-40 top-0 left-0 h-full transition-transform duration-200 ease-in-out transform bg-slate-800 border-r border-slate-700 md:translate-x-0 md:w-80 md:block ${
        open ? "translate-x-0 w-80" : "-translate-x-full w-80 md:translate-x-0 md:w-80"
      }`}
      style={{ willChange: "transform" }}
    >
      <div className="h-full flex flex-col">
        <div className="px-4 py-3 flex items-center justify-between border-b border-slate-700">
          <h2 className="text-lg font-semibold">Contacts</h2>
          <button
            onClick={onToggle}
            aria-label={open ? "Close sidebar" : "Open sidebar"}
            className="p-1 rounded-md hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            {open ? "◀" : "☰"}
          </button>
        </div>

        <div className="flex-1 flex flex-col">
          <div className="p-2 border-b border-slate-700">
            <div className="flex gap-2">
              <div className="flex-1">
                <div className="px-2">
                  <input aria-label="Search contacts" placeholder="Search" className="w-full bg-slate-800 rounded-md px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2" />
                </div>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-auto">
            <div className="p-2">
              <div className="text-slate-400">Contact list loading...</div>
            </div>
          </div>

          <div className="border-t border-slate-700 p-2">
            <button className="w-full bg-slate-700 rounded-md px-3 py-2">Add Contact</button>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default ChatSidebar;
