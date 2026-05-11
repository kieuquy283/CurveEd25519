"use client";
import React from "react";
import { useChatStore } from "@/store/useChatStore";
import { useContactStore } from "@/store/useContactStore";
import { useTrustStore } from "@/store/useTrustStore";
import TrustBadge from "@/components/trust/TrustBadge";
import SettingsDialog from "@/components/settings/SettingsDialog";

interface Props {
  onToggleSidebar: () => void;
}

const ChatTopbar: React.FC<Props> = ({ onToggleSidebar }) => {
  const active = useChatStore((s) => s.activeConversationId);
  const contact = useContactStore((s) => (active ? s.getContact(active) : undefined));

  const [openSettings, setOpenSettings] = React.useState(false);

  return (
    <>
      <header className="h-14 flex items-center px-4 bg-slate-900 border-b border-slate-700">
        <button onClick={onToggleSidebar} className="mr-3 p-2 rounded-md hover:bg-slate-800">
          ☰
        </button>
        <div className="flex-1">
          <h1 className="text-sm font-semibold">{contact?.name ?? "Conversation"}</h1>
        </div>
        <div className="flex items-center gap-3">
          {contact && (
            <div className="mr-2">
              <TrustBadge level={useTrustStore.getState().getEntry(contact.peerId)?.trustLevel} />
            </div>
          )}
          <button onClick={() => setOpenSettings(true)} className="p-2 rounded-md hover:bg-slate-800">⚙</button>
        </div>
      </header>
      {openSettings && (
        // lazy-load the dialog component synchronously
        <SettingsDialog open={openSettings} onClose={() => setOpenSettings(false)} />
      )}
    </>
  );
};

export default ChatTopbar;
