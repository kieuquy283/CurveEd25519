"use client";
import React, { useState } from "react";
import { useContactStore } from "@/store/useContactStore";
import { Contact } from "@/types/models";

export default function AddContactDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [peerId, setPeerId] = useState("");
  const addContact = useContactStore((s) => s.addContact);

  function create() {
    if (!name || !peerId) return;
    const c: Contact = {
      id: `contact-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      name,
      peerId,
      trustLevel: "untrusted",
      isOnline: false,
      createdAt: new Date().toISOString(),
      lastSeen: undefined,
      avatarUrl: undefined,
    };
    addContact(c);
    setOpen(false);
    setName("");
    setPeerId("");
  }

  return (
    <div className="px-3 py-2">
      <button onClick={() => setOpen(true)} className="w-full bg-slate-700 rounded-md px-3 py-2">Add Contact</button>
      {open && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/60">
          <div className="bg-slate-900 p-4 rounded-md w-full max-w-md">
            <h3 className="text-lg font-semibold mb-2">Add Contact</h3>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" className="w-full bg-slate-800 rounded-md px-3 py-2 mb-2" />
            <input value={peerId} onChange={(e) => setPeerId(e.target.value)} placeholder="Peer ID" className="w-full bg-slate-800 rounded-md px-3 py-2 mb-2" />
            <div className="flex justify-end gap-2 mt-2">
              <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-md">Cancel</button>
              <button onClick={create} className="px-3 py-2 bg-indigo-600 rounded-md">Create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
