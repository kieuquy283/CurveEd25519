import { useState } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  contacts: any[];
  onCreate: (contact: any) => void;
};

export default function StartConversationDialog({
  open,
  onClose,
  contacts,
  onCreate,
}: Props) {
  const [search, setSearch] = useState("");

  if (!open) return null;

  const filtered = contacts.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center">
      <div className="bg-zinc-900 w-[400px] rounded-xl p-4">
        <h2 className="text-lg font-semibold mb-4">
          Start Conversation
        </h2>

        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search contact..."
          className="w-full p-2 rounded bg-zinc-800 mb-4"
        />

        <div className="space-y-2 max-h-[300px] overflow-y-auto">
          {filtered.map((contact) => (
            <button
              key={contact.id}
              onClick={() => {
                onCreate(contact);
                onClose();
              }}
              className="w-full text-left p-3 rounded bg-zinc-800 hover:bg-zinc-700"
            >
              {contact.name}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}