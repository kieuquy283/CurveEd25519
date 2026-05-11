"use client";
import React from "react";
import ContactAvatar from "./ContactAvatar";
import { Contact } from "@/types/models";
import { useChatStore } from "@/store/useChatStore";
import TrustBadge from "@/components/trust/TrustBadge";
import { useTrustStore } from "@/store/useTrustStore";

export default function ContactItem({ contact }: { contact: Contact }) {
  const setActive = useChatStore((s) => s.setActiveConversation);
  const convs = useChatStore((s) => s.conversations);
  let unread = 0;
  for (const [, conv] of convs.entries()) {
    if (conv.peerId === contact.peerId) {
      unread = conv.unreadCount ?? 0;
      break;
    }
  }

  return (
    <div
      onClick={() => setActive(contact.peerId)}
      className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-slate-800 cursor-pointer"
    >
      <ContactAvatar src={contact.avatarUrl} alt={contact.name} size={44} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <div className="truncate font-medium flex items-center gap-2">
            <span>{contact.name}</span>
            <TrustBadge level={useTrustStore.getState().getEntry(contact.peerId)?.trustLevel} />
          </div>
          <div className="text-xs text-slate-400">{contact.isOnline ? "●" : "○"}</div>
        </div>
        <div className="text-slate-400 text-sm truncate">{contact.lastSeen ? `Last seen ${contact.lastSeen}` : ""}</div>
      </div>
      {unread > 0 && (
        <div className="bg-rose-600 text-white text-xs px-2 py-1 rounded-full">{unread}</div>
      )}
    </div>
  );
}
