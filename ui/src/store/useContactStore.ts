/**
 * Contacts state store.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { Contact } from "@/types/models";

interface ContactStore {
  contacts: Map<string, Contact>;
  
  addContact: (contact: Contact) => void;
  updateContact: (id: string, partial: Partial<Contact>) => void;
  removeContact: (id: string) => void;
  getContact: (id: string) => Contact | undefined;
  getContacts: () => Contact[];
  searchContacts: (query: string) => Contact[];
  replaceContacts: (contacts: Contact[]) => void;
  isTrustedContact: (peerId: string) => boolean;
  reset: () => void;
}

export const useContactStore = create<ContactStore>()(
  devtools(
    (set, get) => ({
      contacts: new Map(),
      
      addContact: (contact) =>
        set((state) => {
          const newContacts = new Map(state.contacts);
          newContacts.set(contact.id, contact);
          return { contacts: newContacts };
        }),
      
      updateContact: (id, partial) =>
        set((state) => {
          const newContacts = new Map(state.contacts);
          const existing = newContacts.get(id);
          if (existing) {
            newContacts.set(id, { ...existing, ...partial });
          }
          return { contacts: newContacts };
        }),
      
      removeContact: (id) =>
        set((state) => {
          const newContacts = new Map(state.contacts);
          newContacts.delete(id);
          return { contacts: newContacts };
        }),
      
      getContact: (id) => {
        const state = get();
        return state.contacts.get(id);
      },
      
      getContacts: () => {
        const state = get();
        return Array.from(state.contacts.values()).sort((a, b) =>
          a.name.localeCompare(b.name)
        );
      },
      
      searchContacts: (query) => {
        const state = get();
        const q = query.toLowerCase();
        return Array.from(state.contacts.values()).filter(
          (c) =>
            c.name.toLowerCase().includes(q) ||
            c.peerId.toLowerCase().includes(q)
        );
      },

      replaceContacts: (contacts) =>
        set(() => {
          const map = new Map<string, Contact>();
          for (const contact of contacts) {
            map.set(contact.id, contact);
          }
          return { contacts: map };
        }),

      isTrustedContact: (peerId) => {
        const state = get();
        const contact = Array.from(state.contacts.values()).find(
          (c) => c.peerId.toLowerCase() === peerId.toLowerCase()
        );
        return Boolean(contact?.trusted && !contact?.keyChanged);
      },
      
      reset: () => set({ contacts: new Map() }),
    }),
    { name: "ContactStore" }
  )
);
