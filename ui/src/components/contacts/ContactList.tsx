"use client";
import React from "react";
import { useContactStore } from "@/store/useContactStore";
import ContactItem from "./ContactItem";

export default function ContactList() {
  const getContacts = useContactStore((s) => s.getContacts);
  const contacts = getContacts();

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-2 flex flex-col gap-2">
        {contacts.length === 0 ? (
          <div className="text-slate-500 p-3">No contacts</div>
        ) : (
          contacts.map((c) => <ContactItem key={c.id} contact={c} />)
        )}
      </div>
    </div>
  );
}
